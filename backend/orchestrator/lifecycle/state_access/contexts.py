"""SoAI - Mutable lifecycle state access lock contexts [backend/orchestrator/lifecycle/state_access/contexts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.state.circuit_breaker import CircuitBreaker
    from orchestrator.plugin_state import PluginState

__all__ = (
    "CircuitBreakersContext",
    "PluginsContext",
)


@dataclass(slots=True)
class PluginsContext:
    plugin_states: dict[str, PluginState]
    idle_plugins: OrderedDict[str, float]


@dataclass(slots=True)
class CircuitBreakersContext:
    circuit_breakers: dict[str, CircuitBreaker]
    dirty_circuit_breakers: set[str]
