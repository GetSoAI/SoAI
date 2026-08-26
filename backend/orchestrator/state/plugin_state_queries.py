"""SoAI - Plugin state store query helpers [backend/orchestrator/state/plugin_state_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.state.health_status import PluginHealthStatus
from core.state.protocols import ImmutablePluginStates
from core.state.state_names import (
    PLUGIN_STATE_NOT_DETECTED,
    PluginRuntimeStateName,
    resolve_plugin_runtime_state_name,
)
from orchestrator.state.health_updates import apply_plugin_health_status_update
from orchestrator.state.internal_protocols import PluginStateStoreQueryProtocol
from orchestrator.state.snapshot_cache import (
    resolve_snapshot,
    resolve_snapshot_with_version,
)

__all__ = (
    "get_all_plugin_store_states",
    "get_all_plugin_store_states_with_version",
    "get_plugin_store_status",
    "update_plugin_store_health_status",
)

OPERATION = "plugin_state_store.update_health_status"


async def get_plugin_store_status(
    store: PluginStateStoreQueryProtocol,
    plugin_name: str,
) -> PluginRuntimeStateName:
    async with store.global_lock:
        plugin_state = store.plugin_states.get(plugin_name)
        if plugin_state is None:
            return PLUGIN_STATE_NOT_DETECTED
        status_value = plugin_state.get("status")
        if not isinstance(status_value, str) or not status_value:
            return PLUGIN_STATE_NOT_DETECTED
        state = resolve_plugin_runtime_state_name(status_value)
        if state is not None:
            return state
        raise StateError(
            "Invalid stored plugin runtime state.",
            operation="plugin_state_store.get_status",
            details={"plugin_name": plugin_name, "status": status_value},
        )


async def get_all_plugin_store_states(
    store: PluginStateStoreQueryProtocol,
) -> ImmutablePluginStates:
    async with store.global_lock:
        snapshot = resolve_snapshot(store.plugin_states, store.immutable_snapshot_cache)
        store.immutable_snapshot_cache = snapshot
        return snapshot


async def get_all_plugin_store_states_with_version(
    store: PluginStateStoreQueryProtocol,
) -> tuple[ImmutablePluginStates, int]:
    async with store.global_lock:
        snapshot, version = resolve_snapshot_with_version(
            store.plugin_states,
            store.immutable_snapshot_cache,
            store.state_version,
        )
        store.immutable_snapshot_cache = snapshot
        return (snapshot, version)


async def update_plugin_store_health_status(
    store: PluginStateStoreQueryProtocol,
    plugin_name: str,
    health_status: PluginHealthStatus,
) -> None:
    try:
        async with store.plugin_locks.lock(plugin_name):
            async with store.global_lock:
                plugin_state = store.plugin_states.get(plugin_name)
                if plugin_state is None:
                    store.logger.warning(
                        "Attempted to update health status for unknown plugin: %s",
                        plugin_name,
                    )
                    return
                if not apply_plugin_health_status_update(plugin_state, health_status):
                    return
                store.state_version += 1
                store.invalidate_snapshot_cache()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            store.logger,
            exception,
            message=f"Error updating plugin health status for {plugin_name}",
            operation=OPERATION,
        )
