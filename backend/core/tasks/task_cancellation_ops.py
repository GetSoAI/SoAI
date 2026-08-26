"""SoAI - Task cancellation helpers [backend/core/tasks/task_cancellation_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id

__all__ = (
    "cancel_task",
    "generate_system_cancellation_id",
)

LOGGER_NAME = "SoAI.core.tasks.task_cancellation_ops"
OPERATION = "core.tasks.task_cancellation_ops.cancel_task"


def generate_system_cancellation_id(owner: str) -> str:
    owner_value = str(owner or "").strip() or "unknown"
    return create_system_id(subsystem="orchestrator", owner=owner_value, include_random_suffix=True)


async def cancel_task[TaskResult](
    task: asyncio.Task[TaskResult] | None,
    *,
    logger: LoggerProtocol | None = None,
    label: str = "task",
) -> None:
    if task is None or task.done():
        return
    target_logger = logger or get_logger(LOGGER_NAME)
    still_pending = await cancel_and_await(
        [task],
        logger=target_logger,
        task_label=label,
        timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
    )
    if still_pending or task.cancelled():
        return
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            target_logger,
            exception,
            message=f"Unhandled exception while cancelling {label}",
            operation=OPERATION,
        )
