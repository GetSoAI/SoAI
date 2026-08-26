"""SoAI - Orchestrator circuit breaker state management and persistence [backend/orchestrator/lifecycle/circuit_breakers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.state.circuit_breaker import CircuitBreaker, CircuitBreakerState
from core.tasks.periodic import run_periodic_task
from orchestrator.lifecycle.circuit_breaker_config import build_circuit_breaker_config
from orchestrator.lifecycle.circuit_breaker_dependencies import (
    OrchestratorLifecycleCircuitBreakersDependencies,
)
from orchestrator.lifecycle.circuit_breaker_persistence import (
    flush_dirty_circuit_breaker_states,
)
from orchestrator.lifecycle.circuit_breaker_state_events import (
    publish_circuit_breaker_state_change,
)
from orchestrator.lifecycle.circuit_breaker_types import (
    CircuitBreakerSnapshotDict,
    build_circuit_breaker_snapshot,
    circuit_breaker_snapshot_to_json,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
__all__ = ("OrchestratorLifecycleCircuitBreakers",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.circuit_breakers"


class OrchestratorLifecycleCircuitBreakers:
    def __init__(self, deps: OrchestratorLifecycleCircuitBreakersDependencies) -> None:
        self._deps = deps
        self._health_check_config = deps.config.health_check_config

    async def update_config(self, config: OrchestratorRuntimeConfig) -> None:
        self._health_check_config = config.health_check_config
        breaker_config = build_circuit_breaker_config(self._health_check_config)
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            for plugin_name, breaker in breaker_state.circuit_breakers.items():
                if breaker.update_config(**breaker_config):
                    breaker_state.dirty_circuit_breakers.add(plugin_name)

    async def load_circuit_breakers(self) -> None:
        logger = get_logger(LOGGER_NAME)
        states = await self._deps.orchestrator.database_plugins.get_all_circuit_breaker_states()
        breaker_config = build_circuit_breaker_config(self._health_check_config)
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            for state_data in states:
                plugin_name_value = state_data.get("plugin_name")
                if not isinstance(plugin_name_value, str) or not plugin_name_value:
                    continue
                state_value = state_data.get("state")
                if state_value != CircuitBreakerState.CLOSED.value:
                    logger.debug(
                        "Circuit breaker for '%s' was in state '%s'. Resetting to CLOSED as per startup policy.",
                        plugin_name_value,
                        state_value,
                    )
                    breaker_state.dirty_circuit_breakers.add(plugin_name_value)
                breaker_state.circuit_breakers[plugin_name_value] = CircuitBreaker(**breaker_config)
            breaker_count = len(breaker_state.circuit_breakers)
        logger.debug(
            "Initialized %s circuit breakers. All have been reset to CLOSED state for this session.",
            breaker_count,
        )
        await self.flush_dirty_breakers()

    async def persist_dirty_states_loop(self) -> None:
        logger = get_logger(LOGGER_NAME)
        await run_periodic_task(
            self._deps.shutdown_event,
            15,
            self.flush_dirty_breakers,
            logger=logger,
            task_name="persist_dirty_states",
        )

    async def flush_dirty_breakers(self) -> None:
        await flush_dirty_circuit_breaker_states(self._deps)

    def _get_or_create_breaker_in_context(
        self,
        plugin_name: str,
        circuit_breakers: dict[str, CircuitBreaker],
        dirty_circuit_breakers: set[str],
    ) -> CircuitBreaker:
        breaker = circuit_breakers.get(plugin_name)
        if breaker is None:
            breaker_config = build_circuit_breaker_config(self._health_check_config)
            breaker = CircuitBreaker(**breaker_config)
            circuit_breakers[plugin_name] = breaker
            dirty_circuit_breakers.add(plugin_name)
        return breaker

    async def get_all_circuit_breaker_snapshots(self) -> dict[str, JSONDict]:
        snapshots: dict[str, JSONDict] = {}
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            for plugin_name, breaker in breaker_state.circuit_breakers.items():
                snapshot, _ = build_circuit_breaker_snapshot(
                    plugin_name,
                    breaker,
                    check_recovery=False,
                )
                snapshots[plugin_name] = circuit_breaker_snapshot_to_json(snapshot)
        return snapshots

    async def get_circuit_breaker_snapshot(self, plugin_name: str) -> JSONDict:
        did_transition = False
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            breaker = self._get_or_create_breaker_in_context(
                plugin_name,
                breaker_state.circuit_breakers,
                breaker_state.dirty_circuit_breakers,
            )
            snapshot, did_transition = build_circuit_breaker_snapshot(
                plugin_name,
                breaker,
                check_recovery=True,
            )
            if did_transition:
                breaker_state.dirty_circuit_breakers.add(plugin_name)
        if did_transition:
            await publish_circuit_breaker_state_change(self._deps, plugin_name, snapshot)
        return circuit_breaker_snapshot_to_json(snapshot)

    async def is_circuit_breaker_open(self, plugin_name: str) -> bool:
        snapshot: CircuitBreakerSnapshotDict | None = None
        did_transition = False
        is_open_now = False
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            breaker = self._get_or_create_breaker_in_context(
                plugin_name,
                breaker_state.circuit_breakers,
                breaker_state.dirty_circuit_breakers,
            )
            is_open_now, did_transition = breaker.check_and_attempt_recovery()
            if did_transition:
                breaker_state.dirty_circuit_breakers.add(plugin_name)
                snapshot, _ = build_circuit_breaker_snapshot(
                    plugin_name,
                    breaker,
                    check_recovery=False,
                )
        if snapshot is not None:
            await publish_circuit_breaker_state_change(self._deps, plugin_name, snapshot)
        return is_open_now

    async def allow_circuit_breaker_request(self, plugin_name: str) -> bool:
        snapshot: CircuitBreakerSnapshotDict | None = None
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            breaker = self._get_or_create_breaker_in_context(
                plugin_name,
                breaker_state.circuit_breakers,
                breaker_state.dirty_circuit_breakers,
            )
            old_state = breaker.state
            allowed = breaker.allow_request()
            if old_state != breaker.state:
                breaker_state.dirty_circuit_breakers.add(plugin_name)
                snapshot, _ = build_circuit_breaker_snapshot(
                    plugin_name,
                    breaker,
                    check_recovery=False,
                )
        if snapshot is not None:
            await publish_circuit_breaker_state_change(self._deps, plugin_name, snapshot)
        return allowed

    async def _record_breaker_event(self, plugin_name: str, *, is_failure: bool) -> None:
        snapshot: CircuitBreakerSnapshotDict | None = None
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            breaker = self._get_or_create_breaker_in_context(
                plugin_name,
                breaker_state.circuit_breakers,
                breaker_state.dirty_circuit_breakers,
            )
            old_state = breaker.state
            old_failure_count = breaker.failure_count
            old_last_failure_at = breaker.last_failure_at
            if is_failure:
                breaker.record_failure()
                breaker_state.dirty_circuit_breakers.add(plugin_name)
            else:
                breaker.record_success()
                if (
                    breaker.state != old_state
                    or breaker.failure_count != old_failure_count
                    or breaker.last_failure_at != old_last_failure_at
                ):
                    breaker_state.dirty_circuit_breakers.add(plugin_name)
            if old_state != breaker.state:
                snapshot, _ = build_circuit_breaker_snapshot(
                    plugin_name,
                    breaker,
                    check_recovery=False,
                )
        if snapshot:
            await publish_circuit_breaker_state_change(self._deps, plugin_name, snapshot)

    async def record_cb_failure(self, plugin_name: str) -> None:
        await self._record_breaker_event(plugin_name, is_failure=True)

    async def record_cb_success(self, plugin_name: str) -> None:
        await self._record_breaker_event(plugin_name, is_failure=False)

    async def trip_circuit_breaker(self, plugin_name: str) -> None:
        snapshot: CircuitBreakerSnapshotDict | None = None
        async with self._deps.state.circuit_breakers_context() as breaker_state:
            breaker = self._get_or_create_breaker_in_context(
                plugin_name,
                breaker_state.circuit_breakers,
                breaker_state.dirty_circuit_breakers,
            )
            old_state = breaker.state
            old_failure_count = breaker.failure_count
            old_last_failure_at = breaker.last_failure_at
            breaker.force_open()
            if (
                breaker.state != old_state
                or breaker.failure_count != old_failure_count
                or breaker.last_failure_at != old_last_failure_at
            ):
                breaker_state.dirty_circuit_breakers.add(plugin_name)
            snapshot, _ = build_circuit_breaker_snapshot(plugin_name, breaker, check_recovery=False)
        if snapshot is not None:
            await publish_circuit_breaker_state_change(self._deps, plugin_name, snapshot)
