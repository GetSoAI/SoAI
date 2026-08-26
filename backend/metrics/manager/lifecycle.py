"""SoAI - Metrics manager lifecycle operations [backend/metrics/manager/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.logging.trace import get_logger
from core.metrics.protocols import DatabaseMetricsProtocol
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from metrics.manager.types import MetricsWorkerQueueItem

__all__ = (
    "drain_background_queue",
    "finalize_shutdown",
)

LOGGER_NAME = "SoAI.metrics.manager.lifecycle"
OPERATION = "metrics.lifecycle.drain_background_queue"


async def drain_background_queue(
    background_queue: asyncio.Queue[MetricsWorkerQueueItem] | None,
    background_worker_task: asyncio.Task[None] | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if background_queue:
        try:
            await asyncio.wait_for(
                background_queue.put(None),
                timeout=LOCAL_IO_TIMEOUT_SEC,
            )
        except TimeoutError as exception:
            log_exception(
                logger,
                exception,
                message="Metrics shutdown signal timed out; proceeding",
                operation=OPERATION,
                level="warning",
            )
            if background_worker_task and (not background_worker_task.done()):
                background_worker_task.cancel()
    if background_worker_task:
        cleanup_results = await asyncio.gather(background_worker_task, return_exceptions=True)
        for cleanup_result in cleanup_results:
            if isinstance(cleanup_result, BaseException) and not isinstance(
                cleanup_result,
                asyncio.CancelledError,
            ):
                log_handled_exception(
                    logger,
                    cleanup_result,
                    message="Metrics background worker raised during shutdown cleanup (non-critical).",
                    operation=OPERATION,
                    level="warning",
                )
    logger.debug("MetricsManager background queue drained.")


async def finalize_shutdown(
    periodic_tasks: ManagedTaskGroup,
    session_start_time_monotonic_ms: int,
    database_metrics: DatabaseMetricsProtocol,
    flush_genesis_fn: Callable[[], Awaitable[None]],
    flush_metrics_fn: Callable[[], Awaitable[None]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    pending = periodic_tasks.pending()
    msg = f"Cancelling {pending} metrics manager periodic tasks..." if pending else None
    await periodic_tasks.cancel(message=msg)
    session_duration_ms = max(0, monotonic_ms() - int(session_start_time_monotonic_ms))
    await database_metrics.update_genesis_uptime(session_duration_ms)
    await flush_genesis_fn()
    await flush_metrics_fn()
    logger.debug("Final metrics flushed to database.")
    logger.debug("MetricsManager has been shut down.")
