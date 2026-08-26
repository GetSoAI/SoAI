"""SoAI - Plugin readiness gate evaluation [backend/orchestrator/scheduling/plugin_readiness_gates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Container
from dataclasses import dataclass

from core.logging.rate_limited_logger import RateLimitedLogger
from core.state.state_transition_sets import UNAVAILABLE_PLUGIN_STATES
from orchestrator.scheduling.plugin_readiness import (
    PluginReadiness,
    classify_plugin_readiness,
)
from orchestrator.scheduling.plugin_warning_throttles import (
    format_suppressed_warning_suffix,
)

__all__ = (
    "PluginReadinessGate",
    "resolve_deferred_warning_suffix",
    "resolve_plugin_readiness_gate",
    "resolve_plugin_readiness_state",
)


@dataclass(frozen=True, slots=True)
class PluginReadinessGate:
    plugin_status: str
    readiness: PluginReadiness


async def resolve_plugin_readiness_gate(
    *,
    plugin_name: str,
    get_plugin_status: Callable[[str], Awaitable[str]],
    ready_states: Container[str],
    unavailable_states: Container[str] = UNAVAILABLE_PLUGIN_STATES,
) -> PluginReadinessGate:
    plugin_status = await get_plugin_status(plugin_name)
    readiness = classify_plugin_readiness(
        plugin_status,
        ready_states=ready_states,
        unavailable_states=unavailable_states,
    )
    return PluginReadinessGate(plugin_status=plugin_status, readiness=readiness)


async def resolve_plugin_readiness_state(
    *,
    plugin_name: str,
    get_plugin_status: Callable[[str], Awaitable[str]],
    ready_states: Container[str],
    unavailable_states: Container[str] = UNAVAILABLE_PLUGIN_STATES,
) -> tuple[str, PluginReadiness]:
    readiness_gate = await resolve_plugin_readiness_gate(
        plugin_name=plugin_name,
        get_plugin_status=get_plugin_status,
        ready_states=ready_states,
        unavailable_states=unavailable_states,
    )
    return (readiness_gate.plugin_status, readiness_gate.readiness)


def resolve_deferred_warning_suffix(warner: RateLimitedLogger) -> str | None:
    should_emit, suppressed = warner.should_emit()
    if not should_emit:
        return None
    return format_suppressed_warning_suffix(suppressed)
