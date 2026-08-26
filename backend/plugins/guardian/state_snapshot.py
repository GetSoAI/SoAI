"""SoAI - Shared guardian state snapshot parsing helpers [backend/plugins/guardian/state_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.state.state_names import (
    ORCH_STATE_IDLE,
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    PLUGIN_STATE_PERSISTENT_READY,
)
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core.state.protocols import ImmutablePluginStates

__all__ = (
    "GuardianPluginStateSnapshot",
    "build_guardian_plugin_state_snapshot",
    "collect_running_idle_plugin_names",
    "collect_unlocked_plugin_names",
    "get_last_updated_monotonic",
    "get_plugin_status",
    "read_recovery_in_progress",
)

RUNNING_IDLE_STATES: frozenset[str] = frozenset(
    {
        ORCH_STATE_IDLE,
        ORCH_STATE_READY,
        ORCH_STATE_READY_DIRTY,
        PLUGIN_STATE_PERSISTENT_READY,
    },
)


@dataclass(frozen=True, slots=True)
class GuardianPluginStateSnapshot:
    plugin_name: str
    status: str | None
    last_updated_monotonic: float | None


def build_guardian_plugin_state_snapshot(
    state_snapshot: ImmutablePluginStates,
) -> dict[str, GuardianPluginStateSnapshot]:
    parsed: dict[str, GuardianPluginStateSnapshot] = {}
    for plugin_name, plugin_state_info in state_snapshot.items():
        if not isinstance(plugin_name, str) or not plugin_name:
            continue
        status_value = plugin_state_info.get("status")
        last_updated_value = plugin_state_info.get("last_updated_monotonic")
        parsed[plugin_name] = GuardianPluginStateSnapshot(
            plugin_name=plugin_name,
            status=status_value if isinstance(status_value, str) else None,
            last_updated_monotonic=(
                float(last_updated_value) if isinstance(last_updated_value, int | float) else None
            ),
        )
    return parsed


def collect_unlocked_plugin_names(
    self: PluginGuardianInternalProtocol,
    plugin_states: dict[str, GuardianPluginStateSnapshot],
) -> set[str]:
    return {
        plugin_name
        for plugin_name in plugin_states
        if not self.plugin_manager.lifecycle.is_plugin_locked(plugin_name)
    }


async def read_recovery_in_progress(self: PluginGuardianInternalProtocol) -> set[str]:
    async with self.recovery_tasks_lock:
        return set(self.recovery_tasks.keys())


def get_plugin_status(
    plugin_states: dict[str, GuardianPluginStateSnapshot],
    plugin_name: str,
) -> str | None:
    snapshot = plugin_states.get(plugin_name)
    return snapshot.status if snapshot is not None else None


def get_last_updated_monotonic(
    plugin_states: dict[str, GuardianPluginStateSnapshot],
    plugin_name: str,
    *,
    default: float,
) -> float:
    snapshot = plugin_states.get(plugin_name)
    if snapshot is None or snapshot.last_updated_monotonic is None:
        return default
    return snapshot.last_updated_monotonic


def collect_running_idle_plugin_names(
    plugin_states: dict[str, GuardianPluginStateSnapshot],
    candidate_names: Iterable[str],
) -> list[str]:
    return [
        plugin_name
        for plugin_name in candidate_names
        if get_plugin_status(plugin_states, plugin_name) in RUNNING_IDLE_STATES
    ]
