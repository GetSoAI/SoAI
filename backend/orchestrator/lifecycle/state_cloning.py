"""SoAI - Plugin runtime state cloning [backend/orchestrator/lifecycle/state_cloning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from orchestrator.plugin_state import PluginState

__all__ = ("clone_plugin_state",)


def clone_plugin_state(state: PluginState) -> PluginState:
    loaded_parameters = state.loaded_parameters
    active_tasks = state.active_tasks
    return PluginState(
        plugin_name=state.plugin_name,
        loaded_model_universal_id=state.loaded_model_universal_id,
        last_request_universal_id=state.last_request_universal_id,
        loaded_parameters=dict(loaded_parameters) if loaded_parameters else None,
        parameter_version=state.parameter_version,
        last_activity=state.last_activity,
        is_busy=state.is_busy,
        active_tasks=set(active_tasks),
        avg_processing_time_ema=state.avg_processing_time_ema,
        model_load_time=state.model_load_time,
        finalize_pending=state.finalize_pending,
    )
