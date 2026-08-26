"""SoAI - Plugin deletion workflow with backend removal and cleanup [backend/plugins/registry/delete.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import DeletePluginCommand
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.actions.progress import (
    create_task_progress_sender_for_plugin_manager,
    notify_operation_cancelled,
    send_completion_with_task,
    send_success_completion_for_plugin_manager,
)
from plugins.context_ids import resolve_task_id_from_context
from plugins.lifecycle_advisory_lock import plugin_lifecycle_advisory_lock
from plugins.registry.delete_flow import (
    handle_delete_failure_noncritical,
    perform_plugin_deletion,
    resolve_delete_plugin_start_state,
    restore_state_after_delete_cancel_noncritical,
)
from plugins.state.task_collisions import handle_plugin_manager_task_id_collision

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("process_delete_plugin_async",)

LOGGER_NAME = "SoAI.plugins.registry.delete"
OPERATION = "plugin_registry.process_delete_plugin_async"
PLUGIN_DELETE_FLOW_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    NotFoundError,
    StateError,
    ValidationError,
)


async def process_delete_plugin_async(
    self: PluginManagerRuntimeProtocol,
    command: DeletePluginCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name = command.plugin_name
    reply_channel = command.reply_channel
    context = command.context
    display_name = await self.get_plugin_display_name(plugin_name)
    trace_id = context.trace_id if context else "no-context"
    user_id = context.user_id if context else 0
    task_id_value = resolve_task_id_from_context(context)
    try:
        async with (
            plugin_lifecycle_advisory_lock(self, plugin_name),
            self.lifecycle.lifecycle_scope(
                service_name="Plugin manager",
                task_type="delete_plugin",
                plugin_name=plugin_name,
                metadata={"operation": "delete_plugin", "display_name": display_name},
                acquire_plugin_lock=True,
                user_id=user_id,
                task_id=task_id_value,
                context=context,
            ) as (_, task_id),
        ):
            plugin_info_at_start = None
            try:
                progress_callback = create_task_progress_sender_for_plugin_manager(
                    self,
                    reply_channel,
                    task_id,
                )
                if not await validate_action_for_state_async(
                    self,
                    command.plugin_name,
                    "delete",
                    reply_channel,
                    task_id,
                ):
                    return
                (
                    plugin_info_at_start,
                    initial_state,
                    is_incompatible,
                    supports_backend_installation,
                ) = await resolve_delete_plugin_start_state(
                    self,
                    plugin_name=plugin_name,
                    trace_id=trace_id,
                )
                await perform_plugin_deletion(
                    self,
                    plugin_name=plugin_name,
                    reply_channel=reply_channel,
                    task_id=task_id,
                    command=command,
                    initial_state=initial_state,
                    is_incompatible=is_incompatible,
                    supports_backend_installation=supports_backend_installation,
                    progress_callback=progress_callback,
                    context=context,
                )
                message = f"Plugin '{display_name}' has been completely and permanently deleted."
                logger.info(message)
                await send_success_completion_for_plugin_manager(
                    self,
                    reply_channel,
                    task_id,
                    message,
                )
            except asyncio.CancelledError:
                logger.info(
                    "Deletion for plugin '%s' cancelled by user request.",
                    display_name or plugin_name,
                )
                if plugin_info_at_start:
                    await restore_state_after_delete_cancel_noncritical(
                        self,
                        plugin_name=plugin_name,
                        plugin_info_at_start=plugin_info_at_start,
                        trace_id=trace_id,
                        context=context,
                        logger=logger,
                        display_name=display_name,
                    )
                await notify_operation_cancelled(
                    "Plugin deletion",
                    reply_channel,
                    task_id,
                    self.task_registry,
                )
                raise
            except PLUGIN_DELETE_FLOW_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to delete plugin; operation aborted to prevent inconsistent state",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name, "display_name": display_name},
                    level="critical",
                )
                if plugin_info_at_start is not None:
                    await handle_delete_failure_noncritical(
                        self,
                        plugin_name=plugin_name,
                        display_name=display_name,
                        context=context,
                        exception=exception,
                        logger=logger,
                    )
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=False,
                    message=f"Deletion failed and was aborted to prevent corruption. Please check logs. Error: {exception}",
                    task_registry=self.task_registry,
                    send_task_complete_event_callable=self.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
    except TaskIDCollisionError as exception:
        await handle_plugin_manager_task_id_collision(self, exception, reply_channel)
