"""SoAI - Background task logging utilities [backend/core/tasks/logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

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


def log_task_exception[TaskResult](task: asyncio.Task[TaskResult], logger: LoggerProtocol) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.debug("Background task '%s' was cancelled.", task.get_name())
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Unhandled exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    except SoAIError as exception:
        log_handled_exception(
            logger,
            exception,
            message=f"Handled SoAI exception in background task '{task.get_name()}'",
            operation=OPERATION,
            level="warning",
        )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message=f"Unexpected exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message=f"Unclassified exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
    except ExceptionGroup as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            logger,
            coerced,
            message=f"Unhandled grouped exception in background task '{task.get_name()}'",
            operation=OPERATION,
        )
