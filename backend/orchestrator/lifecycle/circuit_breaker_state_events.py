"""SoAI - Circuit breaker state change publishing [backend/orchestrator/lifecycle/circuit_breaker_state_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_plugins import CircuitBreakerStateChangedEvent
from core.state.circuit_breaker import CircuitBreakerState
from orchestrator.lifecycle.circuit_breaker_dependencies import (
    OrchestratorLifecycleCircuitBreakersDependencies,
)
from orchestrator.lifecycle.circuit_breaker_types import (
    CircuitBreakerSnapshotDict,
    resolve_health_status_for_breaker_state,
)

__all__ = ("publish_circuit_breaker_state_change",)


async def publish_circuit_breaker_state_change(
    deps: OrchestratorLifecycleCircuitBreakersDependencies,
    plugin_name: str,
    snapshot: CircuitBreakerSnapshotDict,
) -> None:
    health_status = resolve_health_status_for_breaker_state(CircuitBreakerState(snapshot["state"]))
    await deps.orchestrator.state_aggregator.update_plugin_health_status(plugin_name, health_status)
    await deps.orchestrator.bus.publish(CircuitBreakerStateChangedEvent(**snapshot))
