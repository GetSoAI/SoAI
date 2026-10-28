"""SoAI - Backend update check and automatic mutation admission [backend/plugins/manager/backend_update_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.events.types_system import SoAIMainState
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.state.state_names import PLUGIN_STATE_NOT_DETECTED, PLUGIN_STATE_STOPPED
from plugins.actions.backend_lifecycle_validation import validate_action_for_state_async
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol

__all__ = (
    "backend_update_admission_allowed",
    "backend_update_runtime_idle",
    "backend_update_application_ready",
)


async def backend_update_application_ready(
    manager: PluginManagerRuntimeProtocol, runtime: RuntimeStateStoreProtocol
) -> bool:
    if (
        runtime.shutdown_event.is_set()
        or runtime.system_stop_event.is_set()
        or runtime.repair_plane
        or runtime.restart_pending.is_set()
        or manager.lifecycle.disabled
    ):
        return False
    state = await manager.dependencies.infrastructure.state_aggregator.get_main_state()
    return state.get("state") in {
        SoAIMainState.READY.value,
        SoAIMainState.ACTIVE.value,
        SoAIMainState.ERROR.value,
    }


async def backend_update_admission_allowed(
    manager: PluginManagerRuntimeProtocol, plugin_name: str, *, require_stopped: bool
) -> bool:
    if not await validate_action_for_state_async(
        manager,
        plugin_name,
        "update_backend",
        asyncio.Queue(),
        emit_error_event=False,
        finalize_task=False,
    ):
        return False
    return await backend_update_runtime_idle(manager, plugin_name, require_stopped=require_stopped)


async def backend_update_runtime_idle(
    manager: PluginManagerRuntimeProtocol, plugin_name: str, *, require_stopped: bool
) -> bool:
    state = await manager.dependencies.databases.plugins.get_plugin_state(plugin_name)
    if state == PLUGIN_STATE_NOT_DETECTED or (require_stopped and state != PLUGIN_STATE_STOPPED):
        return False
    lifecycle = manager.orchestrator_lifecycle
    if lifecycle is None:
        return False
    snapshot = await lifecycle.watchers.get_plugin_state(plugin_name)
    if snapshot is None:
        return state == PLUGIN_STATE_STOPPED
    return not snapshot.active_tasks and not snapshot.finalize_pending
