"""SoAI - Circuit breaker lifecycle state shapes [backend/orchestrator/lifecycle/circuit_breaker_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from core.plugins.protocols_database import CircuitBreakerStatePayload
from core.state.circuit_breaker import CircuitBreaker, CircuitBreakerState

if TYPE_CHECKING:
    from core.state.health_status import PluginHealthStatus
    from core.types.json import JSONDict

__all__ = (
    "CircuitBreakerConfigDict",
    "CircuitBreakerSnapshotDict",
    "build_circuit_breaker_payload",
    "build_circuit_breaker_snapshot",
    "circuit_breaker_snapshot_to_json",
    "resolve_health_status_for_breaker_state",
)


class CircuitBreakerConfigDict(TypedDict):
    failure_threshold: int
    recovery_timeout_sec: float
    failure_window_sec: float


class CircuitBreakerSnapshotDict(TypedDict):
    plugin_name: str
    state: str
    failure_count: int
    failure_threshold: int
    last_failure_at_ms: int
    is_open: bool
    recovery_timeout_sec: int
    failure_window_sec: int


def build_circuit_breaker_payload(breaker: CircuitBreaker) -> CircuitBreakerStatePayload:
    return {
        "state": breaker.state,
        "failure_count": breaker.failure_count,
        "last_failure_at_ms": breaker.last_failure_epoch_ms,
    }


def build_circuit_breaker_snapshot(
    plugin_name: str,
    breaker: CircuitBreaker,
    *,
    check_recovery: bool,
) -> tuple[CircuitBreakerSnapshotDict, bool]:
    if check_recovery:
        is_open_now, did_transition = breaker.check_and_attempt_recovery()
    else:
        is_open_now = breaker.state == CircuitBreakerState.OPEN
        did_transition = False
    snapshot: CircuitBreakerSnapshotDict = {
        "plugin_name": plugin_name,
        "state": breaker.state.value,
        "failure_count": breaker.failure_count,
        "last_failure_at_ms": breaker.last_failure_epoch_ms,
        "is_open": is_open_now,
        "recovery_timeout_sec": int(breaker.recovery_timeout_sec),
        "failure_window_sec": int(breaker.failure_window_sec),
        "failure_threshold": breaker.failure_threshold,
    }
    return (snapshot, did_transition)


def circuit_breaker_snapshot_to_json(snapshot: CircuitBreakerSnapshotDict) -> JSONDict:
    return {
        "plugin_name": snapshot["plugin_name"],
        "state": snapshot["state"],
        "failure_count": snapshot["failure_count"],
        "last_failure_at_ms": snapshot["last_failure_at_ms"],
        "is_open": snapshot["is_open"],
        "recovery_timeout_sec": snapshot["recovery_timeout_sec"],
        "failure_window_sec": snapshot["failure_window_sec"],
        "failure_threshold": snapshot["failure_threshold"],
    }


def resolve_health_status_for_breaker_state(state: CircuitBreakerState) -> PluginHealthStatus:
    if state == CircuitBreakerState.OPEN:
        return "open"
    if state == CircuitBreakerState.HALF_OPEN:
        return "recovering"
    return "ok"
