"""SoAI - Snapshot utilities for the orchestrator state aggregator [backend/orchestrator/state/snapshot_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from core.state.state_names import PLUGIN_STATE_NOT_DETECTED

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginState, ImmutablePluginStates
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "create_default_plugin_state",
    "create_immutable_plugin_states_snapshot",
    "get_or_create_plugin_state",
    "shallow_copy_iterable_optional",
    "shallow_copy_mapping_optional",
)


def create_default_plugin_state() -> JSONDict:
    return {
        "status": PLUGIN_STATE_NOT_DETECTED,
        "last_updated_ms": 0,
        "last_updated_monotonic": 0.0,
        "authority": None,
        "reason": "",
        "details": {},
    }


def shallow_copy_mapping_optional[CloneT](
    data: Mapping[str, CloneT] | None,
) -> dict[str, CloneT] | None:
    if data is None:
        return None
    return dict(data)


def shallow_copy_iterable_optional[CloneT](data: Iterable[CloneT] | None) -> list[CloneT] | None:
    if data is None:
        return None
    return list(data)


def _freeze_plugin_state(state: JSONDict) -> ImmutablePluginState:
    details = state.get("details")
    if isinstance(details, dict):
        frozen_state: dict[str, JSONValue] = dict(state)
        frozen_state["details"] = MappingProxyType(dict(details))
        return MappingProxyType(frozen_state)
    return MappingProxyType(state)


def create_immutable_plugin_states_snapshot(
    plugin_states: dict[str, JSONDict],
) -> ImmutablePluginStates:
    return MappingProxyType(
        {name: _freeze_plugin_state(state) for name, state in plugin_states.items()},
    )


def get_or_create_plugin_state(
    plugin_states: dict[str, JSONDict],
    plugin_name: str,
) -> JSONDict:
    if plugin_name not in plugin_states:
        plugin_states[plugin_name] = create_default_plugin_state()
    return plugin_states[plugin_name]
