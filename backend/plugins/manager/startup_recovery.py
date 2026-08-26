"""SoAI - Crash-safe plugin startup recovery helpers [backend/plugins/manager/startup_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_STOPPING,
    ORCH_STATE_UNKNOWN,
    PLUGIN_STATE_STOPPED,
    resolve_plugin_runtime_state_name,
)
from plugins.manager.startup_recovery_stop_sweep import (
    perform_startup_backend_stop_sweep,
)
from plugins.state.startup_recovery_decisions import (
    STARTUP_INTERRUPTED_ACTION_STATES,
    STARTUP_STALE_RUNTIME_STATES,
    resolve_startup_interrupted_action_recovery_state,
)
from plugins.state.transition_publication import transition_plugin_state_and_wait

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "perform_startup_backend_stop_sweep",
    "recover_startup_stale_plugin_states",
)

LOGGER_NAME = "SoAI.plugins.manager.startup_recovery"


async def recover_startup_stale_plugin_states(manager: PluginManagerRuntimeProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    state_aggregator = manager.dependencies.infrastructure.state_aggregator
    if state_aggregator is None:
        raise StateError("Plugin manager requires a StateAggregator instance for startup recovery.")
    plugin_records = await manager.dependencies.databases.plugins.get_all_listable_plugins()
    if not plugin_records:
        return
    current_states = await state_aggregator.get_all_plugin_states()
    stop_sweep = manager.state.lifecycle.startup_recovery_stop_sweep
    stop_sweep.clear()
    for record in plugin_records:
        plugin_name = record.get("plugin_name")
        if not isinstance(plugin_name, str) or not plugin_name.strip():
            continue
        normalized_name = plugin_name.strip()
        plugin_state = current_states.get(normalized_name)
        status_value = plugin_state.get("status") if isinstance(plugin_state, Mapping) else None
        if not isinstance(status_value, str) or not status_value:
            status_value = record.get("state")
        if not isinstance(status_value, str) or not status_value:
            continue
        resolved_state = resolve_plugin_runtime_state_name(status_value)
        if resolved_state is None:
            raise StateError(
                "Invalid persisted plugin runtime state during startup recovery.",
                operation="plugin_manager.startup_recovery",
                details={"plugin_name": normalized_name, "state": status_value},
            )
        status_value = resolved_state
        if status_value in {ORCH_STATE_DISABLED, ORCH_STATE_QUARANTINED}:
            continue
        if status_value in STARTUP_INTERRUPTED_ACTION_STATES:
            recovery_state = resolve_startup_interrupted_action_recovery_state(
                normalized_name,
                status_value,
                operation="plugin_manager.startup_recovery",
                unhandled_message="Unhandled interrupted plugin action state.",
            )
            logger.error(
                "Interrupted plugin action detected on startup for '%s': %s -> %s",
                normalized_name,
                status_value,
                recovery_state,
            )
            await transition_plugin_state_and_wait(
                manager,
                normalized_name,
                recovery_state,
                "Startup recovery: interrupted plugin backend action.",
            )
            continue
        if status_value in STARTUP_STALE_RUNTIME_STATES:
            if bool(record.get("persistent")):
                logger.info(
                    "Persistent plugin runtime state detected on startup for '%s': %s will be resolved by persistent health validation.",
                    normalized_name,
                    status_value,
                )
                continue
            stop_sweep.add(normalized_name)
            if status_value == ORCH_STATE_UNKNOWN:
                logger.warning(
                    "Unknown plugin runtime state detected on startup for '%s': %s -> %s",
                    normalized_name,
                    status_value,
                    PLUGIN_STATE_STOPPED,
                )
                await transition_plugin_state_and_wait(
                    manager,
                    normalized_name,
                    PLUGIN_STATE_STOPPED,
                    "Startup recovery: unknown runtime state after unclean shutdown.",
                )
                continue
            if status_value != ORCH_STATE_STOPPING:
                logger.warning(
                    "Stale runtime plugin state detected on startup for '%s': %s -> %s",
                    normalized_name,
                    status_value,
                    ORCH_STATE_STOPPING,
                )
                await transition_plugin_state_and_wait(
                    manager,
                    normalized_name,
                    ORCH_STATE_STOPPING,
                    "Startup recovery: stale runtime state after unclean shutdown.",
                )
