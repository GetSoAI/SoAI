"""SoAI - State transition graph [backend/core/state/state_transition_graph.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.state.orchestrator_state_transitions import ORCHESTRATOR_STATE_TRANSITIONS
from core.state.state_transitions_data import PLUGIN_STATE_TRANSITIONS

if TYPE_CHECKING:
    from core.state.state_names import PluginRuntimeStateName

__all__ = ("get_valid_state_transitions",)


def get_valid_state_transitions(
    state: PluginRuntimeStateName,
) -> tuple[PluginRuntimeStateName, ...]:
    for source_state, targets in PLUGIN_STATE_TRANSITIONS:
        if source_state == state:
            return targets
    for source_state, targets in ORCHESTRATOR_STATE_TRANSITIONS:
        if source_state == state:
            return targets
    return ()
