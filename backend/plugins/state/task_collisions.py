"""SoAI - Plugin task collision handling [backend/plugins/state/task_collisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from core.tasks.protocols_operations import SendErrorEventCallable

if TYPE_CHECKING:
    from core.events.types_base import Event
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("handle_plugin_manager_task_id_collision", "handle_task_id_collision_error")

LOGGER_NAME = "SoAI.plugins.state.task_collisions"
OPERATION = "plugins.state.task_collisions.cleanup_callback"


async def handle_task_id_collision_error(
    exception: TaskIDCollisionError,
    reply_channel: asyncio.Queue[Event],
    send_error_event_callable: SendErrorEventCallable,
    cleanup_callback: Callable[[], Awaitable[None]] | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if cleanup_callback:
        try:
            await cleanup_callback()
        except RECOVERABLE_EXCEPTIONS as cleanup_error:
            log_handled_exception(
                logger,
                cleanup_error,
                message="Cleanup callback failed during task collision handling (non-critical).",
                operation=OPERATION,
                details={"task_id": exception.task_id},
                level="debug",
            )
    await send_error_event_callable(
        reply_channel,
        f"Task with ID '{exception.task_id}' already exists (status: {exception.existing_status}).",
        ErrorType.CONFLICT,
    )


async def handle_plugin_manager_task_id_collision(
    manager: PluginManagerRuntimeProtocol,
    exception: TaskIDCollisionError,
    reply_channel: asyncio.Queue[Event],
) -> None:
    await handle_task_id_collision_error(
        exception,
        reply_channel,
        manager.dependencies.infrastructure.task_helpers.send_error_event,
    )
