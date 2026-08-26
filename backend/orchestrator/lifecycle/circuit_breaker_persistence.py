"""SoAI - Circuit breaker dirty-state batch persistence to the plugin database [backend/orchestrator/lifecycle/circuit_breaker_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.state.circuit_breaker import CircuitBreakerState
from orchestrator.lifecycle.circuit_breaker_dependencies import (
    OrchestratorLifecycleCircuitBreakersDependencies,
)
from orchestrator.lifecycle.circuit_breaker_types import build_circuit_breaker_payload

if TYPE_CHECKING:
    from core.plugins.protocols_database import CircuitBreakerStatePayload

__all__ = ("flush_dirty_circuit_breaker_states",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.circuit_breaker_persistence"
OPERATION = "orchestrator.lifecycle.circuit_breakers.flush_dirty_breakers"


async def flush_dirty_circuit_breaker_states(
    deps: OrchestratorLifecycleCircuitBreakersDependencies,
) -> None:
    logger = get_logger(LOGGER_NAME)
    payloads_by_plugin: dict[str, CircuitBreakerStatePayload] = {}
    breaker_snapshot_by_plugin: dict[str, tuple[CircuitBreakerState, int, float]] = {}
    missing_plugins: set[str] = set()
    async with deps.state.circuit_breakers_context() as breaker_state:
        if not breaker_state.dirty_circuit_breakers:
            return
        dirty_copy = breaker_state.dirty_circuit_breakers.copy()
        for plugin_name in dirty_copy:
            breaker = breaker_state.circuit_breakers.get(plugin_name)
            if breaker is None:
                missing_plugins.add(plugin_name)
                continue
            payloads_by_plugin[plugin_name] = build_circuit_breaker_payload(breaker)
            breaker_snapshot_by_plugin[plugin_name] = (
                breaker.state,
                breaker.failure_count,
                breaker.last_failure_at,
            )
        for plugin_name in missing_plugins:
            breaker_state.dirty_circuit_breakers.discard(plugin_name)
    if not payloads_by_plugin:
        return
    plugin_names = sorted(payloads_by_plugin.keys())
    tasks = [
        deps.orchestrator.database_plugins.upsert_circuit_breaker_state(
            plugin_name,
            payloads_by_plugin[plugin_name],
        )
        for plugin_name in plugin_names
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failed_plugins: set[str] = set()
    succeeded_plugins: set[str] = set()
    for plugin_name, result in zip(plugin_names, results, strict=True):
        if isinstance(result, BaseException):
            failed_plugins.add(plugin_name)
            log_exception(
                logger,
                result,
                message="Failed to persist circuit breaker state; will retry.",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="warning",
            )
            continue
        succeeded_plugins.add(plugin_name)
    async with deps.state.circuit_breakers_context() as breaker_state:
        for plugin_name in failed_plugins:
            breaker_state.dirty_circuit_breakers.add(plugin_name)
        for plugin_name in succeeded_plugins:
            breaker = breaker_state.circuit_breakers.get(plugin_name)
            snapshot = breaker_snapshot_by_plugin.get(plugin_name)
            if breaker is None or snapshot is None:
                continue
            if (
                breaker.state == snapshot[0]
                and breaker.failure_count == snapshot[1]
                and breaker.last_failure_at == snapshot[2]
            ):
                breaker_state.dirty_circuit_breakers.discard(plugin_name)
