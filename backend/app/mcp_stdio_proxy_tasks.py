"""SoAI - MCP stdio proxy task monitoring [backend/app/mcp_stdio_proxy_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.mcp_stdio_proxy_backpressure import join_inbound_queue, put_inbound_payload
from app.mcp_stdio_proxy_stdout import drain_stdout_writer
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "finalize_stdio_proxy_tasks",
    "stop_stdio_proxy_workers",
    "wait_for_stdio_proxy_completion",
)

OPERATION_PROXY_TASK_BACKGROUND_COMPLETION = "app.mcp_stdio_proxy_tasks.background_completion"


def _build_unexpected_proxy_task_completion_error[Result](
    task: asyncio.Task[None] | asyncio.Task[Result],
) -> StateError:
    task_name = task.get_name()
    if task.cancelled():
        return StateError(
            "MCP stdio proxy background task was cancelled.",
            details={"task": task_name},
            operation=OPERATION_PROXY_TASK_BACKGROUND_COMPLETION,
        )
    exception = task.exception()
    if exception is not None:
        return StateError(
            "MCP stdio proxy background task failed.",
            details={"task": task_name},
            operation=OPERATION_PROXY_TASK_BACKGROUND_COMPLETION,
            cause=exception,
        )
    return StateError(
        "MCP stdio proxy background task stopped unexpectedly.",
        details={"task": task_name},
        operation=OPERATION_PROXY_TASK_BACKGROUND_COMPLETION,
    )


async def _wait_for_task_or_background_failure[Result](
    *,
    awaited_task: asyncio.Task[Result],
    background_tasks: tuple[asyncio.Task[None], ...],
) -> Result:
    pending_tasks: set[asyncio.Task[Result] | asyncio.Task[None]] = {
        awaited_task,
        *background_tasks,
    }
    while True:
        done_tasks, _pending = await asyncio.wait(
            pending_tasks,
            timeout=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done_tasks:
            continue
        completion_error: StateError | None = None
        for done_task in done_tasks:
            if done_task is not awaited_task:
                pending_tasks.remove(done_task)
                task_error = _build_unexpected_proxy_task_completion_error(done_task)
                if completion_error is None:
                    completion_error = task_error
        if completion_error is not None:
            raise completion_error
        if awaited_task in done_tasks:
            pending_tasks.remove(awaited_task)
            return await awaited_task


async def wait_for_stdio_proxy_completion(
    *,
    stdin_task: asyncio.Task[None],
    inbound_queue: asyncio.Queue[JSONDict | None],
    background_tasks: tuple[asyncio.Task[None], ...],
    logger: LoggerProtocol,
) -> None:
    await _wait_for_task_or_background_failure(
        awaited_task=stdin_task,
        background_tasks=background_tasks,
    )
    join_task = create_ephemeral_task(
        join_inbound_queue(inbound_queue),
        name="mcp_stdio_proxy.inbound_join",
        log_exceptions=False,
    )
    try:
        await _wait_for_task_or_background_failure(
            awaited_task=join_task,
            background_tasks=background_tasks,
        )
    finally:
        await uncancel_then_cleanup(
            cancel_and_await(
                (join_task,),
                logger=logger,
                task_label="mcp stdio inbound join",
                timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
            ),
        )


async def stop_stdio_proxy_workers(
    *,
    inbound_queue: asyncio.Queue[JSONDict | None],
    worker_count: int,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    try:
        for _ in range(worker_count):
            await put_inbound_payload(inbound_queue, None)
        await join_inbound_queue(inbound_queue)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="MCP stdio proxy inbound shutdown failed (non-critical).",
            operation=operation,
            level="debug",
        )


async def finalize_stdio_proxy_tasks(
    *,
    stdin_task: asyncio.Task[None],
    producer_tasks: tuple[asyncio.Task[None], ...],
    stdout_queue: asyncio.Queue[str],
    writer_task: asyncio.Task[None],
    logger: LoggerProtocol,
    writer_operation: str,
) -> None:
    pending_producer_count = await uncancel_then_cleanup(
        cancel_and_await(
            (stdin_task, *producer_tasks),
            logger=logger,
            task_label="mcp stdio producer tasks",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        ),
    )
    writer_drained = False
    if pending_producer_count == 0:
        writer_drained = await uncancel_then_cleanup(
            drain_stdout_writer(
                stdout_queue=stdout_queue,
                writer_task=writer_task,
                logger=logger,
                operation=writer_operation,
            ),
        )
    await uncancel_then_cleanup(
        cancel_and_await(
            () if writer_drained else (writer_task,),
            logger=logger,
            task_label="mcp stdio tasks",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        ),
    )
