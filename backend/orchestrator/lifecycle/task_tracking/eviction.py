"""SoAI - Eviction candidate selection algorithm [backend/orchestrator/lifecycle/task_tracking/eviction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.orchestrator.protocols_lifecycle import PluginStateProtocol
from core.state.state_names import ORCH_STATE_ERROR, ORCH_STATE_QUARANTINED
from core.state.state_transition_sets import INTERRUPTIBLE_IDLE_STATES

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates

__all__ = ("select_eviction_candidate",)

SCHEDULER_INACTIVE_STATES = frozenset({ORCH_STATE_QUARANTINED})
EVICTION_HYSTERESIS_SEC = 30.0


def select_eviction_candidate(
    plugin_persistence: Mapping[str, bool],
    *,
    exclude: set[str] | None = None,
    all_states: ImmutablePluginStates,
    idle_plugins_snapshot: list[str],
    plugin_states_snapshot: Mapping[str, PluginStateProtocol],
    queue_empty_snapshot: Mapping[str, bool],
    current_time: float | None = None,
) -> str | None:
    exclude_set = exclude or set()
    time_now = current_time if current_time is not None else time.monotonic()

    for plugin_name, state_data in all_states.items():
        if (
            plugin_name not in exclude_set
            and state_data.get("status") in {ORCH_STATE_ERROR, ORCH_STATE_QUARANTINED}
            and (not plugin_persistence.get(plugin_name))
        ):
            return plugin_name

    for plugin_name in idle_plugins_snapshot:
        if plugin_name in exclude_set:
            continue
        state = plugin_states_snapshot.get(plugin_name)
        if state is None:
            continue
        loaded_model_universal_id = state.loaded_model_universal_id
        if not loaded_model_universal_id:
            continue
        model_load_time = state.model_load_time
        if model_load_time is not None and time_now - model_load_time < EVICTION_HYSTERESIS_SEC:
            continue
        plugin_status = (all_states.get(plugin_name) or {}).get("status")
        if plugin_status in SCHEDULER_INACTIVE_STATES:
            continue
        is_busy = bool(state.is_busy)
        active_tasks = state.active_tasks
        if (
            (not is_busy)
            and (not active_tasks)
            and (plugin_status in INTERRUPTIBLE_IDLE_STATES)
            and queue_empty_snapshot.get(plugin_name, True)
        ):
            return plugin_name

    for plugin_name, state in plugin_states_snapshot.items():
        if plugin_name in exclude_set or plugin_persistence.get(plugin_name):
            continue
        if state is None:
            continue
        is_busy = bool(state.is_busy)
        active_tasks = state.active_tasks
        loaded_model_universal_id = state.loaded_model_universal_id
        if is_busy or active_tasks or (not loaded_model_universal_id):
            continue
        model_load_time = state.model_load_time
        if model_load_time is not None and time_now - model_load_time < EVICTION_HYSTERESIS_SEC:
            continue
        plugin_status = (all_states.get(plugin_name) or {}).get("status")
        if (
            plugin_status in SCHEDULER_INACTIVE_STATES
            or plugin_status not in INTERRUPTIBLE_IDLE_STATES
        ):
            continue
        if not queue_empty_snapshot.get(plugin_name, True):
            continue
        return plugin_name

    return None
