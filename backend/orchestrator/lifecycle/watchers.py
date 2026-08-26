"""SoAI - Orchestrator state transition and eviction tracker [backend/orchestrator/lifecycle/watchers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_base import Event
from core.events.types_plugins import (
    PluginInstallationStateChangedEvent,
    PluginLoadedEvent,
    PluginPurgedEvent,
    PluginRuntimeStateChangedEvent,
    PluginStoppedEvent,
)
from core.orchestrator.protocols_lifecycle import PluginStateProtocol
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.state.circuit_breaker import CircuitBreakerState
from core.state.health_status import PluginHealthStatus
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from orchestrator.lifecycle.event_shutdown.internal_protocols import (
    OrchestratorWatcherEventDependenciesProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleRuntimeMutationsProtocol,
)
from orchestrator.lifecycle.watcher_event_handlers import (
    handle_plugin_purged_event,
    handle_plugin_reloaded_event,
    handle_plugin_stopped_event,
)
from orchestrator.lifecycle.watcher_snapshots import (
    build_status_snapshot,
    clone_plugin_state_snapshot,
    clone_plugin_states_snapshot,
)
from orchestrator.lifecycle.watchers_dependencies import (
    OrchestratorLifecycleWatchersDependencies,
)

__all__ = ("OrchestratorLifecycleWatchers",)


class OrchestratorLifecycleWatchers:
    def __init__(self, deps: OrchestratorLifecycleWatchersDependencies) -> None:
        self.deps: OrchestratorWatcherEventDependenciesProtocol = deps
        self._runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol | None = None

    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None:
        self._runtime_mutations = runtime_mutations

    async def get_idle_plugins_snapshot(self) -> list[str]:
        return [
            plugin_name
            for plugin_name in await self.deps.state.get_idle_plugins_snapshot()
            if plugin_name
        ]

    async def get_idle_plugins_with_timestamps(self) -> list[tuple[str, float]]:
        return [
            (plugin_name, float(idle_since))
            for plugin_name, idle_since in await self.deps.state.get_idle_plugins_with_timestamps()
            if plugin_name
        ]

    async def handle_state_change(self, event: Event) -> None:
        if not isinstance(
            event,
            PluginRuntimeStateChangedEvent | PluginInstallationStateChangedEvent,
        ):
            return
        await self.deps.runtime_state_side_effects.apply_replayed_publication(event)

    async def handle_plugin_stopped(self, event: PluginStoppedEvent) -> list[SchedulerWorkItem]:
        return await handle_plugin_stopped_event(self, event)

    async def handle_plugin_reloaded(self, event: PluginLoadedEvent) -> None:
        await handle_plugin_reloaded_event(self, event)

    async def handle_plugin_purged(self, event: PluginPurgedEvent) -> None:
        await handle_plugin_purged_event(self, event)

    async def discard_plugin_runtime_mutations(self, plugin_name: str) -> None:
        runtime_mutations = self._runtime_mutations
        if runtime_mutations is None:
            return
        await runtime_mutations.discard_plugin(plugin_name)

    async def reconcile_idle_plugins(self, *, add: dict[str, float], remove: set[str]) -> None:
        await self.deps.state.reconcile_idle_plugins(add, remove)

    async def set_plugin_health_status(self, plugin_name: str, health: PluginHealthStatus) -> None:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name:
            await self.deps.orchestrator.state_aggregator.update_plugin_health_status(
                normalized_plugin_name,
                health,
            )

    async def clear_plugin_recovery_attempts(self, plugin_name: str) -> None:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name:
            await self.deps.state.pop_recovery_attempts(normalized_plugin_name)

    async def get_plugin_states_snapshot(
        self,
        plugin_names: set[str] | None = None,
    ) -> dict[str, PluginStateProtocol]:
        async with self.deps.state.plugins_context() as plugin_state:
            return clone_plugin_states_snapshot(plugin_state.plugin_states, plugin_names)

    async def get_plugin_state(self, plugin_name: str) -> PluginStateProtocol | None:
        async with self.deps.state.plugins_context() as plugin_state:
            state = plugin_state.plugin_states.get(plugin_name)
            return clone_plugin_state_snapshot(state)

    async def get_status_snapshot(self) -> JSONDict:
        idle_list = await self.get_idle_plugins_snapshot()
        async with self.deps.state.circuit_breakers_context() as breaker_state:
            circuit_breakers: dict[str, JSONDict] = {
                plugin_name: {
                    "state": breaker.state.value,
                    "failures": breaker.failure_count,
                    "is_open": breaker.state == CircuitBreakerState.OPEN,
                }
                for plugin_name, breaker in breaker_state.circuit_breakers.items()
            }
        health_snapshot = await self.deps.orchestrator.state_aggregator.get_plugin_health_statuses()
        return build_status_snapshot(idle_list, circuit_breakers, health_snapshot)
