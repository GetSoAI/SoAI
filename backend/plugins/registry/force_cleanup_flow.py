"""SoAI - Plugin force cleanup flow helpers [backend/plugins/registry/force_cleanup_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_system import TriggerConfigReconciliationCommand
from core.state.state_names import PLUGIN_STATE_DELETING
from core.state.state_transition_sets import RUNTIME_TERMINATED_STATES
from plugins.actions.backend_lifecycle_stop import stop_plugin_if_running
from plugins.filesystem.managed_models import remove_plugin_managed_models
from plugins.filesystem.runtime_artifacts import remove_plugin_backend_installation
from plugins.manager.artifacts import purge_plugin_from_memory
from plugins.registry.force_cleanup_steps import (
    execute_force_cleanup_step,
    perform_force_cleanup_file_removal,
)
from plugins.state.transition_publication import transition_plugin_state_and_wait

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )
    from plugins.protocols_internal.task_progress.internal_protocols import (
        TaskProgressSenderProtocol,
    )

__all__ = (
    "ensure_plugin_safe_for_force_cleanup",
    "run_force_cleanup_steps",
)

OPERATION = "plugin_registry.process_force_cleanup_plugin_async"
PLUGIN_FORCE_CLEANUP_SAFETY_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (StateError,)


async def ensure_plugin_safe_for_force_cleanup(
    self: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    display_name: str,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str,
    progress_callback: TaskProgressSenderProtocol,
    logger: LoggerProtocol,
) -> None:
    try:
        if (
            await self.dependencies.infrastructure.state_aggregator.get_plugin_status(plugin_name)
            in RUNTIME_TERMINATED_STATES
        ):
            await progress_callback(10, "Plugin process already stopped or not runnable.")
            await progress_callback(20, "Plugin process confirmed safe for cleanup.")
            return
        await stop_plugin_if_running(self, plugin_name, reply_channel, task_id=task_id)
    except PLUGIN_FORCE_CLEANUP_SAFETY_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Force Cleanup: Failed to stop plugin '{display_name}'",
            operation=OPERATION,
        )
        raise StateError(
            "Force cleanup cannot continue because the plugin process was not proven stopped.",
            operation="plugins.registry.force_cleanup.ensure_plugin_safe",
            details={"plugin_name": plugin_name},
        ) from exception


async def run_force_cleanup_steps(
    self: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    display_name: str,
    reply_channel: asyncio.Queue[Event] | None,
    task_id: str,
    context: RequestContext | None,
    progress_callback: TaskProgressSenderProtocol,
    logger: LoggerProtocol,
) -> list[str]:
    cleanup_errors: list[str] = []
    await ensure_plugin_safe_for_force_cleanup(
        self,
        plugin_name=plugin_name,
        display_name=display_name,
        reply_channel=reply_channel,
        task_id=task_id,
        progress_callback=progress_callback,
        logger=logger,
    )
    await transition_plugin_state_and_wait(
        self,
        plugin_name,
        PLUGIN_STATE_DELETING,
        "Forced cleanup initiated.",
        context,
    )

    async def purge_models_step() -> None:
        _ = await self.dependencies.models.model_database_purge_service.purge_models_for_plugin(
            plugin_name,
            self.lifecycle,
        )

    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=25,
        progress_message="Deleting managed model files...",
        error_message=f"Force Cleanup: Failed to delete managed models for '{display_name}'",
        error_label="deleting managed models",
        action_callable=lambda: remove_plugin_managed_models(self, plugin_name),
        abort_on_failure=True,
    )
    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=30,
        progress_message="Purging all model records from database...",
        error_message=f"Force Cleanup: Failed to purge models for '{display_name}'",
        error_label="purging models",
        action_callable=purge_models_step,
        abort_on_failure=True,
    )
    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=60,
        progress_message="Purging plugin from memory...",
        error_message=f"Force Cleanup: Failed to purge from memory '{display_name}'",
        error_label="purging from memory",
        action_callable=lambda: purge_plugin_from_memory(self, plugin_name),
        abort_on_failure=True,
    )
    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=75,
        progress_message="Deleting plugin environment...",
        error_message=f"Force Cleanup: Failed to delete plugin environment for '{display_name}'",
        error_label="deleting plugin environment",
        action_callable=lambda: self.worker_controller.delete_plugin_environment(plugin_name),
        abort_on_failure=True,
    )
    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=80,
        progress_message="Deleting plugin backend installation...",
        error_message=f"Force Cleanup: Failed to delete backend installation for '{display_name}'",
        error_label="deleting backend installation",
        action_callable=lambda: remove_plugin_backend_installation(self, plugin_name),
        abort_on_failure=True,
    )
    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=85,
        progress_message="Permanently deleting plugin files...",
        error_message=f"Force Cleanup: Failed to delete plugin files for '{display_name}'",
        error_label="deleting files",
        action_callable=lambda: perform_force_cleanup_file_removal(self, plugin_name),
        abort_on_failure=True,
    )

    async def delete_record_step() -> None:
        deleted = await self.database_plugins.permanently_delete_plugin_record(plugin_name)
        if (not deleted) and await self.database_plugins.get_plugin_by_name(plugin_name):
            raise StateError(
                "Database record deletion failed during force cleanup.",
                operation="plugins.registry.force_cleanup.delete_record",
                details={"plugin_name": plugin_name},
            )

    await execute_force_cleanup_step(
        progress_callback,
        cleanup_errors,
        progress_percent=95,
        progress_message="Permanently deleting database record...",
        error_message=f"Force Cleanup: Failed to delete main DB record for '{display_name}'",
        error_label="deleting database record",
        action_callable=delete_record_step,
        abort_on_failure=True,
    )
    self.dependencies.infrastructure.metrics_manager.purge_plugin_metrics(plugin_name)
    await self.dependencies.infrastructure.event_bus.publish(
        TriggerConfigReconciliationCommand(
            reason=f"plugin_force_cleaned:{plugin_name}",
            context=context,
        ),
    )
    if cleanup_errors:
        await progress_callback(100, "Cleanup finished with errors.")
    else:
        await progress_callback(100, "Cleanup complete.")
    return cleanup_errors
