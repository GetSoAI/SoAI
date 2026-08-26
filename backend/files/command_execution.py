"""SoAI - File command execution with error handling [backend/files/command_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("execute_or_error",)

LOGGER_NAME = "SoAI.files.command_execution"
OPERATION = "files.command_execution.execute_or_error"


async def execute_or_error(
    reply_channel: asyncio.Queue[Event],
    context: str,
    action: Callable[[], Awaitable[None]],
    *,
    task_registry: TaskRegistryProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await action()
    except (NotFoundError, FileNotFoundError) as exception:
        await send_error_event_and_finalize(
            reply_channel,
            str(exception),
            ErrorType.NOT_FOUND,
            registry=task_registry,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=context,
            operation=OPERATION,
        )
        await send_error_event_and_finalize(
            reply_channel,
            str(exception),
            ErrorType.SERVER_ERROR,
            registry=task_registry,
        )
