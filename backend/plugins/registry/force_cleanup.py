"""SoAI - Plugin forced cleanup including providers and artifacts [backend/plugins/registry/force_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import ForceCleanupPluginCommand
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.actions.progress import (
    create_task_progress_sender_for_plugin_manager,
    notify_operation_cancelled,
    send_completion_with_task,
    send_success_completion_for_plugin_manager,
)
from plugins.context_ids import (
    resolve_task_id_from_context,
    resolve_user_id_from_context,
)
from plugins.registry.force_cleanup_flow import run_force_cleanup_steps
from plugins.state.task_collisions import handle_plugin_manager_task_id_collision

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("process_force_cleanup_plugin_async",)

LOGGER_NAME = "SoAI.plugins.registry.force_cleanup"
OPERATION = "plugin_registry.process_force_cleanup_plugin_async"
PLUGIN_FORCE_CLEANUP_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (StateError, ValidationError)


async def process_force_cleanup_plugin_async(
    self: PluginManagerRuntimeProtocol,
    command: ForceCleanupPluginCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name = command.plugin_name
    reply_channel = command.reply_channel
    context = command.context
    user_id = resolve_user_id_from_context(context)
    task_id_value = resolve_task_id_from_context(context)
    try:
        async with self.lifecycle.lifecycle_scope(
            service_name="Plugin manager",
            task_type="force_cleanup",
            plugin_name=plugin_name,
            acquire_plugin_lock=True,
            user_id=user_id,
            context=context,
            task_id=task_id_value,
        ) as (_, task_id):
            display_name = ""
            try:
                display_name = await self.get_plugin_display_name(plugin_name)
                if not await validate_action_for_state_async(
                    self,
                    command.plugin_name,
                    "force_cleanup",
                    reply_channel,
                    task_id,
                ):
                    return
                plugin_info_at_start = await self.database_plugins.get_plugin_by_name(plugin_name)
                if not plugin_info_at_start:
                    raise ValidationError(f"Plugin '{plugin_name}' does not exist in the database.")
                progress_callback = create_task_progress_sender_for_plugin_manager(
                    self,
                    reply_channel,
                    task_id,
                )
                try:
                    logger.critical(
                        "Starting FORCE CLEANUP for plugin '%s'. This is a destructive recovery operation.",
                        display_name,
                    )
                    await progress_callback(5, f"Starting forced cleanup for '{display_name}'...")
                    cleanup_errors = await run_force_cleanup_steps(
                        self,
                        plugin_name=plugin_name,
                        reply_channel=reply_channel,
                        display_name=display_name,
                        task_id=task_id,
                        context=command.context,
                        progress_callback=progress_callback,
                        logger=logger,
                    )
                    if not cleanup_errors:
                        message = (
                            f"Plugin '{display_name}' has been forcefully and completely removed."
                        )
                        logger.info(message)
                        await send_success_completion_for_plugin_manager(
                            self,
                            reply_channel,
                            task_id,
                            message,
                        )
                    else:
                        await send_completion_with_task(
                            reply_channel,
                            task_id,
                            success=False,
                            message=f"Force cleanup for '{display_name}' completed with errors. Some resources may remain. Failures: {', '.join(cleanup_errors)}.",
                            task_registry=self.task_registry,
                            send_task_complete_event_callable=self.dependencies.infrastructure.task_helpers.send_task_complete_event,
                        )
                except PLUGIN_FORCE_CLEANUP_EXCEPTIONS as exception:
                    log_exception(
                        logger,
                        exception,
                        message=f"A catastrophic, unexpected error occurred during force cleanup for '{display_name}'",
                        operation=OPERATION,
                    )
                    await send_completion_with_task(
                        reply_channel,
                        task_id,
                        success=False,
                        message=f"A catastrophic setup error occurred: {exception}",
                        task_registry=self.task_registry,
                        send_task_complete_event_callable=self.dependencies.infrastructure.task_helpers.send_task_complete_event,
                    )
            except asyncio.CancelledError:
                logger.info(
                    "Force cleanup for plugin '%s' cancelled by user request.",
                    display_name or plugin_name,
                )
                await notify_operation_cancelled(
                    "Force cleanup",
                    reply_channel,
                    task_id,
                    self.task_registry,
                    send_task_complete_event_callable=self.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
                raise
            except PLUGIN_FORCE_CLEANUP_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Error during force cleanup",
                    operation=OPERATION,
                    details={"plugin": display_name or plugin_name},
                )
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=False,
                    message=f"Failed to process force cleanup command: {exception}",
                    task_registry=self.task_registry,
                    send_task_complete_event_callable=self.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
    except TaskIDCollisionError as exception:
        await handle_plugin_manager_task_id_collision(self, exception, reply_channel)
