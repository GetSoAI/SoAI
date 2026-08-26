"""SoAI - Watcher snapshot projection helpers [backend/orchestrator/lifecycle/watcher_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.orchestrator.protocols_lifecycle import PluginStateProtocol
from core.types.json import JSONDict
from orchestrator.lifecycle.state_cloning import clone_plugin_state
from orchestrator.plugin_state import PluginState

if TYPE_CHECKING:
    from core.state.health_status import PluginHealthStatus

__all__ = (
    "build_status_snapshot",
    "clone_plugin_state_snapshot",
    "clone_plugin_states_snapshot",
)


def clone_plugin_state_snapshot(state: PluginState | None) -> PluginStateProtocol | None:
    return clone_plugin_state(state) if state is not None else None


def clone_plugin_states_snapshot(
    plugin_states: dict[str, PluginState],
    plugin_names: set[str] | None = None,
) -> dict[str, PluginStateProtocol]:
    if plugin_names is None:
        return {name: clone_plugin_state(state) for name, state in plugin_states.items()}
    return {
        name: clone_plugin_state(state)
        for name, state in plugin_states.items()
        if name in plugin_names
    }


def build_status_snapshot(
    idle_plugins: list[str],
    circuit_breakers: dict[str, JSONDict],
    health_snapshot: dict[str, PluginHealthStatus],
) -> JSONDict:
    return {
        "idle_plugins_list": list(idle_plugins),
        "idle_plugins_count": len(idle_plugins),
        "circuit_breakers": circuit_breakers,
        "plugin_health_statuses": health_snapshot,
    }
