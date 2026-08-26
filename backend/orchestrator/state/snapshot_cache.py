"""SoAI - Plugin state snapshot cache helpers [backend/orchestrator/state/snapshot_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.protocols import ImmutablePluginStates
from core.types.json import JSONDict
from orchestrator.state.snapshot_builder import create_immutable_plugin_states_snapshot

__all__ = (
    "resolve_snapshot",
    "resolve_snapshot_with_version",
)


def resolve_snapshot(
    plugin_states: dict[str, JSONDict],
    cached_snapshot: ImmutablePluginStates | None,
) -> ImmutablePluginStates:
    if cached_snapshot is not None:
        return cached_snapshot
    return create_immutable_plugin_states_snapshot(plugin_states)


def resolve_snapshot_with_version(
    plugin_states: dict[str, JSONDict],
    cached_snapshot: ImmutablePluginStates | None,
    state_version: int,
) -> tuple[ImmutablePluginStates, int]:
    if cached_snapshot is not None:
        return (cached_snapshot, state_version)
    return (create_immutable_plugin_states_snapshot(plugin_states), state_version)
