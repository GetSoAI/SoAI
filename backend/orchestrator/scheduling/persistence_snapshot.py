"""SoAI - Scheduler plugin persistence snapshot helpers [backend/orchestrator/scheduling/persistence_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.plugins.protocols import PluginManagerProtocol

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates

__all__ = ("build_plugin_persistence_snapshot",)


async def build_plugin_persistence_snapshot(
    plugin_manager: PluginManagerProtocol,
    all_states: ImmutablePluginStates,
    *,
    inactive_states: frozenset[str],
) -> tuple[dict[str, bool], int]:
    plugin_names = list(all_states.keys())
    instances = []
    if plugin_names:
        plugin_instance_tasks = [plugin_manager.get_plugin_instance(name) for name in plugin_names]
        instances = await asyncio.gather(*plugin_instance_tasks, return_exceptions=False)
    plugin_persistence = {
        name: inst.PERSISTENT if inst else False
        for name, inst in zip(plugin_names, instances, strict=True)
    }
    active_non_persistent = sum(
        (
            1
            for name, data in all_states.items()
            if not plugin_persistence.get(name) and data.get("status") not in inactive_states
        ),
    )
    return (plugin_persistence, active_non_persistent)
