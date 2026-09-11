"""SoAI - Plugin state generation fencing [backend/core/state/plugin_state_generation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.state.protocols import ImmutablePluginStates

__all__ = (
    "PluginStateGeneration",
    "read_plugin_state_generation",
)


@dataclass(frozen=True, slots=True)
class PluginStateGeneration:
    status: str | None
    last_updated_monotonic: float


def read_plugin_state_generation(
    plugin_states: ImmutablePluginStates,
    plugin_name: str,
) -> PluginStateGeneration | None:
    plugin_state = plugin_states.get(plugin_name)
    if plugin_state is None:
        return None
    status_value = plugin_state.get("status")
    last_updated_value = plugin_state.get("last_updated_monotonic")
    if not isinstance(last_updated_value, int | float):
        return None
    return PluginStateGeneration(
        status=status_value if isinstance(status_value, str) else None,
        last_updated_monotonic=float(last_updated_value),
    )
