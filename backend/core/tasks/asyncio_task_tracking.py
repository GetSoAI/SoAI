"""SoAI - Tracked task registration and rollback helpers [backend/core/tasks/asyncio_task_tracking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger

__all__ = (
    "cancel_and_await_tracked_task",
    "track_task_or_cancel",
)

LOGGER_NAME = "SoAI.core.tasks.asyncio_task_tracking"
OPERATION = "core.tasks.asyncio_task_spawner.create_tracked_and_track_task"


async def cancel_and_await_tracked_task[TaskResult](
    task: asyncio.Task[TaskResult],
    *,
    logger: LoggerProtocol | None,
) -> None:
    await cancel_and_await(
        [task],
        logger=logger,
        task_label="tracked task",
        timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
    )


async def track_task_or_cancel[TaskResult](
    task: asyncio.Task[TaskResult],
    *,
    track_task: Callable[[asyncio.Task[TaskResult]], None],
    logger: LoggerProtocol | None,
    cancellation_id: str,
    owner: str,
) -> None:
    try:
        track_task(task)
    except asyncio.CancelledError as exception:
        exception.add_note("Tracked task wrapper was cancelled.")
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        task_logger = get_logger(LOGGER_NAME)
        coerced_exception = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            task_logger,
            coerced_exception,
            message="Failed to register linked task in tracker. Cancelling task.",
            operation=OPERATION,
            details={
                "cancellation_id": str(cancellation_id),
                "owner": str(owner),
            },
            level="warning",
        )
        await cancel_and_await_tracked_task(task, logger=logger)
        raise
