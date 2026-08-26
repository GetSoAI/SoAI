"""SoAI - Ephemeral async task creation with safety-net error tracking [backend/core/concurrency/ephemeral_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.awaitable_cleanup import create_task_with_rejection_cleanup

__all__ = ("create_ephemeral_task", "spawn_ephemeral_task")

OPERATION = "core.concurrency.ephemeral_tasks"


_EPHEMERAL_LOGGER_NAME = "SoAI.core.concurrency.ephemeral_tasks"


def _on_ephemeral_task_done[ResultT](task: asyncio.Task[ResultT]) -> None:
    if task.cancelled():
        return
    exception: BaseException | None = None
    try:
        exception = task.exception()
    except asyncio.CancelledError:
        return
    except asyncio.InvalidStateError:
        return
    if exception is None:
        return
    logger = get_logger(_EPHEMERAL_LOGGER_NAME)
    task_name = task.get_name()
    if isinstance(exception, RECOVERABLE_EXCEPTIONS):
        log_handled_exception(
            logger,
            exception,
            message="Ephemeral task completed with exception (non-critical).",
            operation=OPERATION,
            level="debug",
            details={"task_name": task_name},
        )
        return
    if isinstance(exception, Exception):
        coerced = coerce_to_soai_error(
            exception,
            operation="core.concurrency.ephemeral_tasks",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Ephemeral task completed with unexpected exception (non-critical).",
            operation=OPERATION,
            level="debug",
            details={"task_name": task_name},
        )
        return
    logger.debug(
        "Ephemeral task '%s' raised: %s",
        task_name,
        type(exception).__name__,
    )


def _register_ephemeral_task[ResultT](
    task: asyncio.Task[ResultT],
    *,
    log_exceptions: bool,
) -> asyncio.Task[ResultT]:
    if log_exceptions:
        task.add_done_callback(_on_ephemeral_task_done)
    return task


def create_ephemeral_task[ResultT](
    coro: Coroutine[None, None, ResultT],
    *,
    name: str | None = None,
    log_exceptions: bool = True,
) -> asyncio.Task[ResultT]:
    task = create_task_with_rejection_cleanup(
        coro,
        name=name,
        rejection_cleanup=(coro,),
    )
    return _register_ephemeral_task(task, log_exceptions=log_exceptions)


def spawn_ephemeral_task[ResultT](
    coro: Coroutine[None, None, ResultT],
    *,
    name: str | None = None,
    log_exceptions: bool = True,
) -> None:
    task = create_task_with_rejection_cleanup(
        coro,
        name=name,
        rejection_cleanup=(coro,),
    )
    if log_exceptions:
        task.add_done_callback(_on_ephemeral_task_done)
