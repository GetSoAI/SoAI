"""SoAI - Named background task scheduling helper [backend/core/concurrency/background_task_scheduling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = ("schedule_named_background_task",)


def schedule_named_background_task(
    coro: Coroutine[None, None, None],
    *,
    name: str,
    track_task: Callable[[asyncio.Task[None]], None],
    logger: LoggerProtocol,
    operation: str,
    empty_name_error_message: str,
    close_failure_message: str,
) -> asyncio.Task[None]:
    task_name = name.strip()
    if not task_name:
        try:
            coro.close()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message=close_failure_message,
                operation=operation,
                level="debug",
            )
        raise ValidationError(empty_name_error_message)
    try:
        task = asyncio.create_task(coro, name=task_name)
    except RECOVERABLE_EXCEPTIONS:
        try:
            coro.close()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message=close_failure_message,
                operation=operation,
                details={"task_name": task_name},
                level="debug",
            )
        raise
    track_task(task)
    return task
