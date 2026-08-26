"""SoAI - Guardian check context assembly [backend/plugins/guardian/check_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.types.json import JSONDict
from plugins.guardian.state_snapshot import (
    GuardianPluginStateSnapshot,
    build_guardian_plugin_state_snapshot,
    collect_unlocked_plugin_names,
    read_recovery_in_progress,
)
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

__all__ = (
    "GuardianCheckContext",
    "build_guardian_check_context",
)


@dataclass(frozen=True, slots=True)
class GuardianCheckContext:
    plugin_states: dict[str, GuardianPluginStateSnapshot]
    unlocked_plugins: set[str]
    recovery_in_progress: set[str]
    active_inferences: list[JSONDict]
    busy_plugins: set[str]


def _collect_busy_plugins(active_inferences: list[JSONDict]) -> set[str]:
    busy_plugins: set[str] = set()
    for info in active_inferences:
        plugin_name_value = info.get("plugin_name")
        if isinstance(plugin_name_value, str) and plugin_name_value:
            busy_plugins.add(plugin_name_value)
    return busy_plugins


async def build_guardian_check_context(
    self: PluginGuardianInternalProtocol,
) -> GuardianCheckContext:
    state_snapshot = await self.state_aggregator.get_all_plugin_states()
    plugin_states = build_guardian_plugin_state_snapshot(state_snapshot)
    active_inferences = await self.executor.get_active_inferences_snapshot()
    return GuardianCheckContext(
        plugin_states=plugin_states,
        unlocked_plugins=collect_unlocked_plugin_names(self, plugin_states),
        recovery_in_progress=await read_recovery_in_progress(self),
        active_inferences=active_inferences,
        busy_plugins=_collect_busy_plugins(active_inferences),
    )
