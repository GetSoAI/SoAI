"""SoAI - Plugin deletion flow helpers [backend/plugins/registry/delete_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.concurrency.deadlines import is_deadline_expired
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import publication_completion_deadline
from core.events.types_plugins import DeletePluginCommand, RemovePluginBackendCommand
from core.events.types_system import TriggerConfigReconciliationCommand
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_DELETING,
    PLUGIN_STATE_NOT_DETECTED,
)
from core.state.state_transition_sets import RUNTIME_TERMINATED_STATES
from core.timing.constants import SHORT_POLL_INTERVAL_SEC
from plugins.actions.backend_lifecycle_execution import execute_lifecycle_task
from plugins.actions.backend_lifecycle_state import require_runtime_state
from plugins.actions.backend_lifecycle_stop import stop_plugin_if_running
from plugins.filesystem.managed_models import remove_plugin_managed_models
from plugins.filesystem.runtime_artifacts import (
    remove_plugin_artifacts,
)
from plugins.manager.artifacts import purge_plugin_from_memory
from plugins.manager.compatibility import compatibility_from_record
from plugins.path_safety import get_plugin_file_path
from plugins.state.transition_publication import transition_plugin_state_and_wait

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )
    from plugins.protocols_internal.task_progress.internal_protocols import (
        TaskProgressSenderProtocol,
    )

__all__ = (
    "handle_delete_failure_noncritical",
    "perform_plugin_deletion",
    "resolve_delete_plugin_start_state",
    "restore_state_after_delete_cancel_noncritical",
)

OPERATION = "plugin_registry.process_delete_plugin_async"
OPERATION_AUTHORITATIVE_STATE_CATCH_UP = (
    "plugin_registry.process_delete_plugin_async.authoritative_state_catch_up"
)
PLUGIN_DELETE_RECOVERY_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (StateError, ValidationError)


async def _wait_for_authoritative_delete_start_state(
    self: PluginManagerRuntimeProtocol,
    plugin_name: str,
    expected_state: str,
    deadline_monotonic: float,
) -> None:
    state_aggregator = self.dependencies.infrastructure.state_aggregator
    while True:
        projected_state = await state_aggregator.get_plugin_status(plugin_name)
        if projected_state == expected_state:
            return
        if is_deadline_expired(deadline_monotonic):
            raise ServiceUnavailableError(
                "Timed out waiting for authoritative plugin state reconciliation.",
                operation=OPERATION_AUTHORITATIVE_STATE_CATCH_UP,
                details={
                    "plugin_name": plugin_name,
                    "projected_state": projected_state,
                    "durable_state": expected_state,
                },
            )
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)


async def resolve_delete_plugin_start_state(
    self: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    trace_id: str,
) -> tuple[JSONDict, str, bool, bool]:
    plugin_info_at_start = await self.database_plugins.get_plugin_by_name(plugin_name)
    if not plugin_info_at_start:
        raise ValidationError(f"Plugin '{plugin_name}' does not exist in the database.")
    state_value = plugin_info_at_start.get("state")
    initial_state = (
        require_runtime_state(
            state_value,
            operation="plugin_registry.process_delete_plugin_async.initial_state",
            plugin_name=plugin_name,
            trace_id=trace_id,
        )
        if isinstance(state_value, str) and state_value
        else PLUGIN_STATE_NOT_DETECTED
    )
    compatibility_check = compatibility_from_record(plugin_info_at_start)
    is_incompatible = bool(compatibility_check.reason and (not compatibility_check.is_overridden))
    supports_backend_installation = bool(
        plugin_info_at_start.get("supports_backend_installation", False),
    )
    return plugin_info_at_start, initial_state, is_incompatible, supports_backend_installation


async def restore_state_after_delete_cancel_noncritical(
    self: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    plugin_info_at_start: JSONDict,
    trace_id: str,
    context: RequestContext | None,
    logger: LoggerProtocol,
    display_name: str,
) -> None:
    try:
        state_value = plugin_info_at_start.get("state")
        restored_state = (
            require_runtime_state(
                state_value,
                operation="plugin_registry.process_delete_plugin_async.cancelled",
                plugin_name=plugin_name,
                trace_id=trace_id,
            )
            if isinstance(state_value, str) and state_value
            else PLUGIN_STATE_NOT_DETECTED
        )
        await transition_plugin_state_and_wait(
            self,
            plugin_name,
            restored_state,
            "Plugin deletion cancelled.",
            context,
        )
    except PLUGIN_DELETE_RECOVERY_EXCEPTIONS as transition_error:
        log_exception(
            logger,
            transition_error,
            message="Failed to restore state after deletion cancellation",
            operation=OPERATION,
            details={"plugin": display_name or plugin_name},
        )


async def perform_plugin_deletion(
    self: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    reply_channel: asyncio.Queue[Event],
    task_id: str,
    command: DeletePluginCommand,
    initial_state: str,
    is_incompatible: bool,
    supports_backend_installation: bool,
    progress_callback: TaskProgressSenderProtocol,
    context: RequestContext | None,
) -> None:
    publication_deadline = publication_completion_deadline()
    plugin_archive_exists = os.path.exists(get_plugin_file_path(self, plugin_name))
    await progress_callback(5, "Checking plugin runtime state before deletion...")
    if (not is_incompatible) and initial_state not in RUNTIME_TERMINATED_STATES:
        await stop_plugin_if_running(
            self,
            plugin_name,
            reply_channel,
            task_id=task_id,
            exclude_cancellation_ids=frozenset((task_id,)),
        )
    else:
        await progress_callback(20, "Plugin is already stopped or not runnable.")
        await _wait_for_authoritative_delete_start_state(
            self,
            plugin_name,
            initial_state,
            publication_deadline,
        )
    await transition_plugin_state_and_wait(
        self,
        plugin_name,
        PLUGIN_STATE_DELETING,
        "Plugin deletion initiated.",
        context,
        completion_deadline_monotonic=publication_deadline,
    )
    if supports_backend_installation and (not is_incompatible) and plugin_archive_exists:
        await progress_callback(25, "Permanently deleting backend...")
        backend_removed = await execute_lifecycle_task(
            self,
            RemovePluginBackendCommand(
                plugin_name=plugin_name,
                delete_models=command.delete_models,
                reply_channel=reply_channel,
                context=context,
            ),
            "remove_backend",
            send_completion_event=False,
            is_part_of_delete=True,
            task_id=task_id,
        )
        if not backend_removed:
            raise StateError("Backend removal failed; refusing to delete plugin records or files.")
    elif supports_backend_installation and (not is_incompatible):
        await progress_callback(
            25,
            "Plugin archive already moved or deleted; skipping plugin-instance backend teardown.",
        )
    elif supports_backend_installation and is_incompatible:
        await progress_callback(
            25,
            "Skipping backend removal because the plugin is incompatible with this SoAI version.",
        )
    backend_removed_models = supports_backend_installation and (not is_incompatible)
    if command.delete_models and (not backend_removed_models):
        await progress_callback(30, "Deleting managed model files...")
        await remove_plugin_managed_models(self, plugin_name)
        await progress_callback(35, "Purging model records from database...")
        await self.dependencies.models.model_database_purge_service.purge_models_for_plugin(
            plugin_name,
            self.lifecycle,
        )
    await progress_callback(60, "Purging plugin from memory and waiting for system cleanup...")
    await purge_plugin_from_memory(self, plugin_name)
    await progress_callback(75, "Deleting plugin environment...")
    await self.worker_controller.delete_plugin_environment(plugin_name)
    await progress_callback(85, "Permanently deleting plugin files...")
    await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
    await remove_plugin_artifacts(self, plugin_name)
    await self.dependencies.infrastructure.config_manager.delete_from_cache(plugin_name)
    await progress_callback(95, "Atomically deleting all database records for plugin...")
    deleted = await self.database_plugins.permanently_delete_plugin_record(plugin_name)
    if (not deleted) and await self.database_plugins.get_plugin_by_name(plugin_name) is not None:
        raise StateError(
            "FATAL: Database atomic deletion failed and record still exists. Aborting.",
        )
    self.dependencies.infrastructure.metrics_manager.purge_plugin_metrics(plugin_name)
    await self.dependencies.infrastructure.event_bus.publish(
        TriggerConfigReconciliationCommand(reason=f"plugin_deleted:{plugin_name}", context=context),
    )


async def handle_delete_failure_noncritical(
    self: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    display_name: str,
    context: RequestContext | None,
    exception: BaseException,
    logger: LoggerProtocol,
) -> None:
    try:
        plugin_exists = await self.database_plugins.get_plugin_by_name(plugin_name)
        target_state = (
            PLUGIN_STATE_DELETE_ERROR if plugin_exists else PLUGIN_STATE_BACKEND_NOT_INSTALLED
        )
        target_message = (
            f"Deletion failed critically: {exception}"
            if plugin_exists
            else "Deletion completed despite error state."
        )
        await transition_plugin_state_and_wait(
            self,
            plugin_name,
            target_state,
            target_message,
            context,
        )
    except PLUGIN_DELETE_RECOVERY_EXCEPTIONS as final_exception:
        log_exception(
            logger,
            final_exception,
            message=("Failed to apply recovery state after plugin delete failure."),
            operation=OPERATION,
            details={"plugin_name": display_name or plugin_name},
            level="critical",
        )
