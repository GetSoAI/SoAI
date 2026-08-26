"""SoAI - MCP worker transfer with progress tracking [backend/mcp/worker/transfer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.progress.formatting import (
    calculate_eta,
    format_transfer_details,
    format_transfer_status_message,
)
from core.progress.speed import SpeedCalculator
from core.tasks.status_transitions import update_progress
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from mcp.progress_reporting import compute_progress_update

if TYPE_CHECKING:
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("run_local_transfer_with_progress",)

LOGGER_NAME = "SoAI.mcp.worker.transfer"
OPERATION_MCP_WORKER_RUN_LOCAL_TRANSFER_WITH_PROGRESS_CLEANUP = (
    "mcp.worker.run_local_transfer_with_progress.cleanup"
)
OPERATION_MCP_WORKER_RUN_LOCAL_TRANSFER_WITH_PROGRESS_REPORT = (
    "mcp.worker.run_local_transfer_with_progress.report"
)
OPERATION_MCP_WORKER_RUN_LOCAL_TRANSFER_WITH_PROGRESS_UPDATE_PROGRESS = (
    "mcp.worker.run_local_transfer_with_progress.update_progress"
)


async def run_local_transfer_with_progress(
    self: MCPWorkerProtocol,
    task_id: str,
    *,
    action: str,
    label: str,
    progress_start: int,
    progress_end: int,
    total_bytes: int | None,
    transfer_function: Callable[[Callable[[int, int | None], None]], int],
) -> int:
    logger = get_logger(LOGGER_NAME)
    loop = asyncio.get_running_loop()
    progress_queue: asyncio.Queue[tuple[int, int | None] | None] = asyncio.Queue(maxsize=1000)

    def _safe_put(item: tuple[int, int | None] | None) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            progress_queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.debug("Progress queue full for task %s, dropping update", task_id)

    def _report(bytes_done: int, total_override: int | None = None) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            loop.call_soon_threadsafe(_safe_put, (bytes_done, total_override))
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to report transfer progress update (non-critical).",
                operation=OPERATION_MCP_WORKER_RUN_LOCAL_TRANSFER_WITH_PROGRESS_REPORT,
                details={"task_id": task_id},
                level="debug",
            )

    speed_calc = SpeedCalculator()
    last_reported_percent = -1
    last_reported_at = 0.0
    last_reported_bytes = 0
    current_total = int(total_bytes) if total_bytes is not None else None

    async def _pump() -> None:
        logger = get_logger(LOGGER_NAME)
        nonlocal last_reported_percent, last_reported_at, last_reported_bytes, current_total
        while True:
            item = await progress_queue.get()
            try:
                if item is None:
                    return
                bytes_done, total_override = item
                if total_override is not None and int(total_override) > 0:
                    current_total = int(total_override)
                scaled_percent, should_report, timestamp = compute_progress_update(
                    current=bytes_done,
                    total=current_total,
                    progress_start=progress_start,
                    progress_end=progress_end,
                    last_reported_percent=last_reported_percent,
                    last_reported_at=last_reported_at,
                    last_reported_bytes=last_reported_bytes,
                )
                if not should_report:
                    continue
                speed = speed_calc.update(bytes_done)
                eta_seconds = (
                    calculate_eta(speed, bytes_done, current_total)
                    if current_total and current_total > 0
                    else 0.0
                )
                message = format_transfer_status_message(
                    action,
                    label,
                    downloaded_size=bytes_done,
                    total_size=current_total,
                    speed=speed,
                    eta_seconds=eta_seconds,
                )
                details = format_transfer_details(
                    bytes_done,
                    current_total,
                    speed=speed,
                    eta_seconds=eta_seconds,
                )
                last_reported_percent = scaled_percent
                last_reported_at = timestamp
                last_reported_bytes = bytes_done
                try:
                    await update_progress(
                        self.task_registry,
                        task_id,
                        progress_current=scaled_percent,
                        status_message=message,
                        details=details,
                    )
                except RECOVERABLE_EXCEPTIONS as progress_err:
                    log_handled_exception(
                        logger,
                        progress_err,
                        message="Task progress update failed during local transfer (non-critical).",
                        operation=OPERATION_MCP_WORKER_RUN_LOCAL_TRANSFER_WITH_PROGRESS_UPDATE_PROGRESS,
                        details={"task_id": task_id},
                        level="debug",
                    )
            finally:
                progress_queue.task_done()

    pump_task = create_ephemeral_task(_pump())

    async def _drain_threadsafe_callbacks() -> None:
        fut = loop.create_future()
        loop.call_soon(fut.set_result, None)
        await fut

    size: int | None = None
    try:
        _safe_put((0, current_total))
        size = int(await asyncio.to_thread(transfer_function, _report))
        return size
    finally:
        cancelled_exception: asyncio.CancelledError | None = None
        try:
            await _drain_threadsafe_callbacks()
            if size is not None:
                _safe_put((size, current_total))
            put_nowait_with_overwrite(progress_queue, None, overwrite_attempts=5)
        except RECOVERABLE_EXCEPTIONS as cleanup_err:
            log_handled_exception(
                logger,
                cleanup_err,
                message="Transfer cleanup failed (non-critical).",
                operation=OPERATION_MCP_WORKER_RUN_LOCAL_TRANSFER_WITH_PROGRESS_CLEANUP,
                details={"task_id": task_id},
                level="debug",
            )
        try:
            done, _pending = await asyncio.wait(
                {pump_task},
                timeout=LOCAL_IO_TIMEOUT_SEC,
            )
            if not done:
                logger.debug(
                    "Transfer pump task did not stop within timeout (task_id=%s)",
                    task_id,
                )
        except asyncio.CancelledError as exception:
            cancelled_exception = exception
        if not pump_task.done():
            await cancel_and_await(
                [pump_task],
                logger=logger,
                task_label="transfer pump task",
                timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            )
        if cancelled_exception is not None:
            raise cancelled_exception
