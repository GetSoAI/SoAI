"""SoAI - Scheduler plugin readiness classification [backend/orchestrator/scheduling/plugin_readiness.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass

from core.state.state_transition_sets import UNAVAILABLE_PLUGIN_STATES

__all__ = (
    "PluginReadiness",
    "classify_plugin_readiness",
)


@dataclass(frozen=True, slots=True)
class PluginReadiness:
    ready: bool
    unavailable: bool

    @property
    def deferred(self) -> bool:
        return (not self.ready) and (not self.unavailable)


def classify_plugin_readiness(
    plugin_status: str,
    *,
    ready_states: Container[str],
    unavailable_states: Container[str] = UNAVAILABLE_PLUGIN_STATES,
) -> PluginReadiness:
    return PluginReadiness(
        ready=plugin_status in ready_states,
        unavailable=plugin_status in unavailable_states,
    )
