"""SoAI - Orchestrator lifecycle state access protocols [backend/orchestrator/lifecycle/state_access/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Protocol

from core.errors.error_types import ErrorType
from core.models.model_context import ModelContext
from core.orchestrator.routing_config import RoutingConfig, VirtualModelConfig
from core.runtime.request_context import RequestContext
from orchestrator.lifecycle.state_access.contexts import (
    CircuitBreakersContext,
    PluginsContext,
)
from orchestrator.plugin_state import PluginState

if TYPE_CHECKING:
    from core.state.circuit_breaker import CircuitBreaker

__all__ = (
    "KillablePluginProcessProtocol",
    "LifecycleStateAccessorProtocol",
    "PluginWorkPurgeProtocol",
    "RoutingConfigProviderProtocol",
    "StartablePluginManagerProtocol",
)


class KillablePluginProcessProtocol(Protocol):
    plugin_name: str

    async def get_backend_process_pids(self) -> list[int]: ...


class StartablePluginManagerProtocol(Protocol):
    plugin_name: str

    async def start_with_model(
        self,
        model_context: ModelContext,
        request_context: RequestContext,
    ) -> bool: ...

    async def health_ping(self) -> tuple[bool, str]: ...

    async def get_backend_process_pids(self) -> list[int]: ...


class PluginWorkPurgeProtocol(Protocol):
    async def __call__(
        self,
        *,
        plugin_name: str,
        purge_reason: str,
        fail_reason: str,
        error_type: ErrorType,
        operation: str,
    ) -> None: ...


class LifecycleStateAccessorProtocol(Protocol):
    async def pop_plugin_state(self, plugin_name: str) -> PluginState | None: ...
    async def update_plugin_state(
        self,
        plugin_name: str,
        updater: Callable[[PluginState], None],
    ) -> PluginState | None: ...
    async def reset_plugin_runtime_state(self, plugin_name: str) -> None: ...
    async def get_idle_plugins_snapshot(self) -> list[str]: ...
    async def get_idle_plugins_with_timestamps(self) -> list[tuple[str, float]]: ...
    async def set_idle_plugin(
        self,
        plugin_name: str,
        timestamp: float,
        *,
        prioritize: bool = False,
    ) -> None: ...
    async def pop_idle_plugin(self, plugin_name: str) -> float | None: ...
    async def reconcile_idle_plugins(self, add: dict[str, float], remove: set[str]) -> None: ...
    async def pop_circuit_breaker(self, plugin_name: str) -> CircuitBreaker | None: ...
    async def increment_recovery_attempts(self, plugin_name: str) -> int: ...
    async def pop_recovery_attempts(self, plugin_name: str) -> int | None: ...
    async def get_virtual_model_map(self) -> dict[str, VirtualModelConfig]: ...
    async def set_virtual_model_maps(
        self,
        virtual_model_map: dict[str, VirtualModelConfig],
        dependency_map: dict[str, set[str]],
    ) -> None: ...
    async def get_virtual_model_dependencies(self, universal_id: str) -> set[str]: ...
    async def remove_lock_entries(self, plugin_name: str) -> None: ...
    def plugins_context(self) -> AbstractAsyncContextManager[PluginsContext]: ...
    def circuit_breakers_context(
        self,
    ) -> AbstractAsyncContextManager[CircuitBreakersContext]: ...
    async def clear_finalize_pending(self, plugin_name: str) -> None: ...
    async def wait_for_finalize_complete(self, plugin_name: str, timeout: float) -> bool: ...
    async def mark_finalize_started(self, plugin_name: str) -> None: ...
    async def signal_finalize_complete(self, plugin_name: str) -> None: ...


class RoutingConfigProviderProtocol(Protocol):
    @property
    def routing_config(self) -> RoutingConfig: ...

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None: ...
