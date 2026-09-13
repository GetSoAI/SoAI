"""SoAI - Task progress/complete helpers for plugin actions [backend/plugins/actions/progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.api_events import send_task_complete_event, send_task_progress_event

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.protocols_operations import (
        SendTaskCompleteEventCallable,
        SendTaskProgressEventCallable,
    )
    from core.types.json import JSONDict, JSONValue
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )
    from plugins.protocols_internal.task_progress.internal_protocols import (
        TaskProgressSenderProtocol,
    )

__all__ = (
    "create_task_progress_sender",
    "create_task_progress_sender_for_plugin_manager",
    "notify_operation_cancelled",
    "send_completion_with_task",
    "send_completion_with_task_for_plugin_manager",
    "send_progress_with_task",
    "send_success_completion_for_plugin_manager",
    "send_unexpected_error_completion_for_plugin_manager",
)

LOGGER_NAME = "SoAI.plugins.actions.progress"
OPERATION_PLUGIN_ACTIONS_NOTIFY_OPERATION_CANCELLED = "plugin_actions.notify_operation_cancelled"
OPERATION_PLUGIN_ACTIONS_SEND_COMPLETION_WITH_TASK = "plugin_actions.send_completion_with_task"
OPERATION_PLUGIN_ACTIONS_SEND_PROGRESS_WITH_TASK = "plugin_actions.send_progress_with_task"


async def send_progress_with_task(
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    percent: int,
    message: str,
    task_registry: TaskRegistryProtocol,
    send_task_progress_event_callable: SendTaskProgressEventCallable | None = None,
    details: JSONValue | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    registry = task_registry
    try:
        if reply_channel is None and task_id is None:
            return
        if reply_channel:
            if task_id:
                bound = registry.resolve_task_identity_for_reply_queue(reply_channel)
                if bound is None or bound[0] != task_id:
                    _ = await registry.attach_reply_queue(task_id, reply_channel)
            progress_callable = send_task_progress_event_callable or send_task_progress_event
            await progress_callable(
                reply_channel,
                percent=percent,
                message=message,
                details=details,
                task_id=task_id,
                registry=registry,
            )
        elif task_id:
            progress_callable = send_task_progress_event_callable or send_task_progress_event
            await progress_callable(
                None,
                percent=percent,
                message=message,
                details=details,
                task_id=task_id,
                registry=registry,
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to emit task progress event",
            operation=OPERATION_PLUGIN_ACTIONS_SEND_PROGRESS_WITH_TASK,
            details={"task_id": task_id},
        )


async def send_completion_with_task(
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    *,
    success: bool,
    message: str,
    result: JSONDict | None = None,
    cancelled: bool = False,
    error_code: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    mutation_fencing_token: int | None = None,
    task_registry: TaskRegistryProtocol,
    send_task_complete_event_callable: SendTaskCompleteEventCallable | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    registry = task_registry
    try:
        if reply_channel is None and task_id is None:
            return
        if reply_channel and task_id:
            bound = registry.resolve_task_identity_for_reply_queue(reply_channel)
            if bound is None or bound[0] != task_id:
                _ = await registry.attach_reply_queue(task_id, reply_channel)
        complete_callable = send_task_complete_event_callable or send_task_complete_event
        await complete_callable(
            reply_channel,
            message,
            success=success,
            task_id=task_id,
            result=result,
            cancelled=cancelled,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
            mutation_fencing_token=mutation_fencing_token,
            registry=registry,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to emit task completion event",
            operation=OPERATION_PLUGIN_ACTIONS_SEND_COMPLETION_WITH_TASK,
            details={"task_id": task_id},
        )


async def send_completion_with_task_for_plugin_manager(
    manager: PluginManagerRuntimeProtocol,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    *,
    success: bool,
    message: str,
    result: JSONDict | None = None,
    cancelled: bool = False,
    error_code: int | None = None,
    error_message: str | None = None,
    mutation_fencing_token: int | None = None,
) -> None:
    await send_completion_with_task(
        reply_channel,
        task_id,
        success=success,
        message=message,
        result=result,
        cancelled=cancelled,
        error_code=error_code,
        error_message=error_message,
        mutation_fencing_token=mutation_fencing_token,
        task_registry=manager.task_registry,
        send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
    )


async def send_unexpected_error_completion_for_plugin_manager(
    manager: PluginManagerRuntimeProtocol,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    exception: Exception,
) -> None:
    error = coerce_to_soai_error(exception, trace_id=task_id)
    public_error = project_public_exception(error, trace_id=task_id)
    message = "The plugin operation failed. Check the selected resource and server diagnostics, then retry."
    await send_completion_with_task(
        reply_channel,
        task_id,
        success=False,
        message=message,
        error_code=error.http_status,
        error_type=str(public_error.code),
        error_message=message,
        task_registry=manager.task_registry,
        send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
    )


async def send_success_completion_for_plugin_manager(
    manager: PluginManagerRuntimeProtocol,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    message: str,
) -> None:
    await send_completion_with_task_for_plugin_manager(
        manager,
        reply_channel,
        task_id,
        success=True,
        message=message,
    )


def create_task_progress_sender(
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    task_registry: TaskRegistryProtocol,
    send_task_progress_event_callable: SendTaskProgressEventCallable | None = None,
) -> TaskProgressSenderProtocol:
    async def progress_sender(percent: int, message: str, details: JSONValue | None = None) -> None:
        await send_progress_with_task(
            reply_channel,
            task_id,
            percent,
            message,
            task_registry,
            send_task_progress_event_callable,
            details=details,
        )

    return progress_sender


def create_task_progress_sender_for_plugin_manager(
    manager: PluginManagerRuntimeProtocol,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
) -> TaskProgressSenderProtocol:
    return create_task_progress_sender(
        reply_channel,
        task_id,
        manager.task_registry,
        manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
    )


async def notify_operation_cancelled(
    operation_name: str,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str | None,
    task_registry: TaskRegistryProtocol,
    send_task_complete_event_callable: SendTaskCompleteEventCallable | None = None,
    mutation_fencing_token: int | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=False,
            message=f"{operation_name} cancelled.",
            cancelled=True,
            mutation_fencing_token=mutation_fencing_token,
            task_registry=task_registry,
            send_task_complete_event_callable=send_task_complete_event_callable,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to notify {operation_name.lower()} cancellation",
            operation=OPERATION_PLUGIN_ACTIONS_NOTIFY_OPERATION_CANCELLED,
        )
