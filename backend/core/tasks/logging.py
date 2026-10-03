"""SoAI - Background task logging utilities [backend/core/tasks/logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import (
    HANDLED_RUNTIME_EXCEPTIONS,
    UNEXPECTED_RUNTIME_EXCEPTIONS,
)
from core.logging.protocols import LoggerProtocol

__all__ = ("log_task_exception",)

OPERATION = "task_helper.log_task_exception"


def _unhandled_exception_kind(exception: BaseException) -> str:
    return "grouped exception" if isinstance(exception, ExceptionGroup) else "exception"


def log_task_exception[TaskResult](task: asyncio.Task[TaskResult], logger: LoggerProtocol) -> None:
    exception: BaseException | None
    try:
        exception = task.exception()
    except asyncio.CancelledError:
        logger.debug("Background task '%s' was cancelled.", task.get_name())
        return
    except asyncio.InvalidStateError as state_error:
        exception = state_error
    if exception is None:
        return
    if isinstance(exception, TaskCancelledError):
        logger.debug("Background task '%s' was cancelled.", task.get_name())
    elif isinstance(exception, RECOVERABLE_EXCEPTIONS):
        log_exception(
            logger,
            exception,
            message=f"Unhandled exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    elif isinstance(exception, SoAIError):
        log_handled_exception(
            logger,
            exception,
            message=f"Handled SoAI exception in background task '{task.get_name()}'",
            operation=OPERATION,
            level="warning",
        )
    elif isinstance(exception, UNEXPECTED_RUNTIME_EXCEPTIONS):
        log_exception(
            logger,
            coerce_to_soai_error(exception, operation=OPERATION),
            message=f"Unexpected exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    elif isinstance(exception, HANDLED_RUNTIME_EXCEPTIONS):
        log_exception(
            logger,
            coerce_to_soai_error(exception, operation=OPERATION),
            message=f"Unclassified exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    elif isinstance(exception, Exception):
        exception_kind = _unhandled_exception_kind(exception)
        log_exception(
            logger,
            coerce_to_soai_error(exception, operation=OPERATION),
            message=f"Unhandled {exception_kind} in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    else:
        raise exception
