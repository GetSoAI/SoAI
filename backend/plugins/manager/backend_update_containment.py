"""SoAI - Backend update worker containment and runtime truth [backend/plugins/manager/backend_update_containment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exceptions import ProcessError, StateError
from core.plugins.backend_update_records import BACKEND_UPDATE_CONTAINMENT_REQUIRED
from core.runtime.backend_process_tracking_db import cleanup_tracked_backend_processes_from_database
from core.runtime.soai_identifiers import create_system_id
from core.state.state_names import (
    ORCH_STATE_IDLE,
    ORCH_STATE_LOADING,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_READY_PENDING_DISPATCH,
    ORCH_STATE_STARTING,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    PLUGIN_STATE_PERSISTENT_READY,
)
from plugins.manager.instances import clear_loaded_plugin_state
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
from plugins.state.transition_publication import transition_plugin_state_and_wait

__all__ = ("contain_backend_update_worker", "record_backend_update_containment_failure")


async def contain_backend_update_worker(
    manager: PluginManagerRuntimeProtocol, plugin_name: str
) -> None:
    await clear_loaded_plugin_state(manager, plugin_name)
    result = await cleanup_tracked_backend_processes_from_database(
        manager.dependencies.databases.plugins, plugin_name=plugin_name, logger=manager.logger
    )
    if result is not None and not result.succeeded:
        raise ProcessError("Backend update subprocess containment failed.")
    await manager.dependencies.databases.plugins.update_plugin_runtime_loaded(plugin_name, False)
    await run_joined_thread_call(
        manager.dependencies.core.log_manager.detach_streaming_handler_from_plugin,
        plugin_name,
        task_name="backend-update-detach-log-stream",
    )
    state = await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
        plugin_name
    )
    if state in {
        ORCH_STATE_IDLE,
        ORCH_STATE_LOADING,
        ORCH_STATE_PROCESSING,
        ORCH_STATE_READY,
        ORCH_STATE_READY_DIRTY,
        ORCH_STATE_READY_PENDING_DISPATCH,
        ORCH_STATE_STARTING,
        PLUGIN_STATE_PERSISTENT_READY,
    }:
        await transition_plugin_state_and_wait(
            manager, plugin_name, ORCH_STATE_STOPPING, "Backend check worker was contained."
        )
        state = ORCH_STATE_STOPPING
    if state == ORCH_STATE_STOPPING:
        await transition_plugin_state_and_wait(
            manager, plugin_name, ORCH_STATE_STOPPED, "Backend check worker containment completed."
        )


async def record_backend_update_containment_failure(
    manager: PluginManagerRuntimeProtocol, plugin_name: str
) -> None:
    async with manager.dependencies.infrastructure.config_manager.plugin_config_mutation_scope(
        plugin_name, operation="plugins.manager.backend_update_containment"
    ):
        database = manager.dependencies.databases.plugins
        record = await database.get_backend_update(plugin_name)
        if record is None:
            raise StateError("Backend containment requires its persisted check identity.")
        failed = replace(
            record,
            status="check_failed",
            failure_code=BACKEND_UPDATE_CONTAINMENT_REQUIRED,
            check_id=create_system_id(subsystem="backend-update", include_random_suffix=True),
        )
        if not await database.commit_backend_update(record, failed):
            raise StateError("Backend containment recovery ownership changed.")
        manager.state.catalog.backend_update_publication_pending = True
        manager.state.catalog.backend_update_wake.set()
