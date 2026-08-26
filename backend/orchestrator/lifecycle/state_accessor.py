"""SoAI - Orchestrator lifecycle state accessor with thread-safe locks [backend/orchestrator/lifecycle/state_accessor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import OrderedDict, defaultdict
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager

from core.orchestrator.routing_config import VirtualModelConfig
from core.state.circuit_breaker import CircuitBreaker
from core.validation.strings import coerce_optional_trimmed_str
from orchestrator.lifecycle.state_access.contexts import (
    CircuitBreakersContext,
    PluginsContext,
)
from orchestrator.plugin_state import PluginState

__all__ = ("LifecycleStateAccessor",)


class _FinalizeEventRegistry:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, plugin_name: str) -> asyncio.Event:
        async with self._lock:
            if plugin_name not in self._events:
                self._events[plugin_name] = asyncio.Event()
                self._events[plugin_name].set()
            return self._events[plugin_name]

    async def signal_finalize_complete(self, plugin_name: str) -> None:
        async with self._lock:
            event = self._events.get(plugin_name)
            if event is not None:
                event.set()

    async def mark_finalize_started(self, plugin_name: str) -> None:
        async with self._lock:
            if plugin_name not in self._events:
                self._events[plugin_name] = asyncio.Event()
            self._events[plugin_name].clear()

    async def remove(self, plugin_name: str) -> None:
        async with self._lock:
            event = self._events.pop(plugin_name, None)
            if event is not None:
                event.set()


class LifecycleStateAccessor:
    def __init__(self) -> None:
        self._plugin_states: dict[str, PluginState] = {}
        self._idle_plugins: OrderedDict[str, float] = OrderedDict()
        self._plugin_recovery_attempts: defaultdict[str, int] = defaultdict(int)
        self._plugins_lock = asyncio.Lock()
        self._plugin_status_lock = asyncio.Lock()
        self._circuit_breaker_lock = asyncio.Lock()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._dirty_circuit_breakers: set[str] = set()
        self._virtual_models_lock = asyncio.Lock()
        self._virtual_model_map: dict[str, VirtualModelConfig] = {}
        self._virtual_model_dependency_map: defaultdict[str, set[str]] = defaultdict(set)
        self._finalize_events = _FinalizeEventRegistry()

    async def pop_plugin_state(self, plugin_name: str) -> PluginState | None:
        async with self._plugins_lock:
            return self._plugin_states.pop(plugin_name, None)

    async def update_plugin_state(
        self,
        plugin_name: str,
        updater: Callable[[PluginState], None],
    ) -> PluginState | None:
        async with self._plugins_lock:
            state = self._plugin_states.get(plugin_name)
            if state is not None:
                updater(state)
            return state

    async def reset_plugin_runtime_state(self, plugin_name: str) -> None:
        async with self._plugins_lock:
            state = self._plugin_states.get(plugin_name)
            if state is not None:
                state.loaded_model_universal_id = None
                state.last_request_universal_id = None
                state.loaded_parameters = None
                state.parameter_version = None
            self._idle_plugins.pop(plugin_name, None)

    async def get_idle_plugins_snapshot(self) -> list[str]:
        async with self._plugins_lock:
            return list(self._idle_plugins.keys())

    async def get_idle_plugins_with_timestamps(self) -> list[tuple[str, float]]:
        async with self._plugins_lock:
            return list(self._idle_plugins.items())

    async def set_idle_plugin(
        self,
        plugin_name: str,
        timestamp: float,
        *,
        prioritize: bool = False,
    ) -> None:
        async with self._plugins_lock:
            self._idle_plugins[plugin_name] = timestamp
            if prioritize:
                self._idle_plugins.move_to_end(plugin_name, last=False)

    async def pop_idle_plugin(self, plugin_name: str) -> float | None:
        async with self._plugins_lock:
            return self._idle_plugins.pop(plugin_name, None)

    async def reconcile_idle_plugins(self, add: dict[str, float], remove: set[str]) -> None:
        async with self._plugins_lock:
            for name, ts in add.items():
                self._idle_plugins[name] = ts
            for name in remove:
                self._idle_plugins.pop(name, None)

    async def pop_circuit_breaker(self, plugin_name: str) -> CircuitBreaker | None:
        async with self._circuit_breaker_lock:
            self._dirty_circuit_breakers.discard(plugin_name)
            return self._circuit_breakers.pop(plugin_name, None)

    async def increment_recovery_attempts(self, plugin_name: str) -> int:
        async with self._plugin_status_lock:
            self._plugin_recovery_attempts[plugin_name] += 1
            return self._plugin_recovery_attempts[plugin_name]

    async def pop_recovery_attempts(self, plugin_name: str) -> int | None:
        async with self._plugin_status_lock:
            return self._plugin_recovery_attempts.pop(plugin_name, None)

    async def get_virtual_model_map(self) -> dict[str, VirtualModelConfig]:
        async with self._virtual_models_lock:
            return dict(self._virtual_model_map)

    async def set_virtual_model_maps(
        self,
        virtual_model_map: dict[str, VirtualModelConfig],
        dependency_map: dict[str, set[str]],
    ) -> None:
        async with self._virtual_models_lock:
            self._virtual_model_map = virtual_model_map
            self._virtual_model_dependency_map = defaultdict(set, dependency_map)

    async def get_virtual_model_dependencies(self, universal_id: str) -> set[str]:
        async with self._virtual_models_lock:
            return set(self._virtual_model_dependency_map.get(universal_id, set()))

    async def remove_lock_entries(self, plugin_name: str) -> None:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name:
            await self._finalize_events.remove(normalized_plugin_name)

    @asynccontextmanager
    async def plugins_context(self) -> AsyncGenerator[PluginsContext]:
        async with self._plugins_lock:
            yield PluginsContext(
                plugin_states=self._plugin_states,
                idle_plugins=self._idle_plugins,
            )

    async def clear_finalize_pending(self, plugin_name: str) -> None:
        async with self._plugins_lock:
            plugin_state = self._plugin_states.get(plugin_name)
            if plugin_state is not None:
                plugin_state.finalize_pending = False

    async def wait_for_finalize_complete(self, plugin_name: str, timeout: float) -> bool:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name is None:
            return True
        event = await self._finalize_events.get_or_create(normalized_plugin_name)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    async def mark_finalize_started(self, plugin_name: str) -> None:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name is None:
            return
        await self._finalize_events.mark_finalize_started(normalized_plugin_name)

    async def signal_finalize_complete(self, plugin_name: str) -> None:
        normalized_plugin_name = coerce_optional_trimmed_str(plugin_name)
        if normalized_plugin_name is None:
            return
        await self._finalize_events.signal_finalize_complete(normalized_plugin_name)

    @asynccontextmanager
    async def circuit_breakers_context(self) -> AsyncGenerator[CircuitBreakersContext]:
        async with self._circuit_breaker_lock:
            yield CircuitBreakersContext(
                circuit_breakers=self._circuit_breakers,
                dirty_circuit_breakers=self._dirty_circuit_breakers,
            )
