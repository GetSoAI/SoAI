"""SoAI - Core state subsystem protocols [backend/core/state/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.state.circuit_breaker import CircuitBreakerState
from core.state.protocols_publication import RuntimeStatePublicationSideEffectsProtocol

if TYPE_CHECKING:
    from core.events.types_plugins import (
        PluginInstallationStateChangedEvent,
        PluginRuntimeStateChangedEvent,
    )
    from core.events.types_system import SoAIMainState
    from core.runtime.request_context import RequestContext
    from core.state.health_status import PluginHealthStatus
    from core.state.state_names import PluginRuntimeStateName
    from core.types.json import JSONDict, JSONValue

    type ImmutablePluginState = Mapping[str, JSONValue]
    type ImmutablePluginStates = Mapping[str, ImmutablePluginState]
else:
    ImmutablePluginState = Mapping
    ImmutablePluginStates = Mapping

__all__ = (
    "AuthoritativePluginStateTransitionReceipt",
    "AuthoritativePluginStateTransitionsProtocol",
    "CircuitBreakerProtocol",
    "RestartStateManagerProtocol",
    "SearchDataStoreProtocol",
    "StateAggregatorProtocol",
    "SystemRestartRequesterProtocol",
)


@dataclass(frozen=True, slots=True)
class AuthoritativePluginStateTransitionReceipt:
    event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent
    completion_waiter: asyncio.Future[None]

    async def wait_for_completion(self, _deadline_monotonic: float) -> None: ...


class CircuitBreakerProtocol(Protocol):
    state: CircuitBreakerState

    def check_and_attempt_recovery(self) -> tuple[bool, bool]: ...

    def is_open(self) -> bool: ...

    def allow_request(self) -> bool: ...

    def record_failure(self) -> None: ...

    def record_success(self) -> None: ...


class RestartStateManagerProtocol(Protocol):
    async def require_restart(self, reason: str, source: str = "unknown") -> None: ...

    async def clear_restart_requirement(self, reason: str = "restart_completed") -> None: ...

    async def check_and_clear_stale_state(self) -> bool: ...

    def get_restart_info(self) -> JSONDict: ...


class SystemRestartRequesterProtocol(Protocol):
    async def require_restart(self, reason: str, source: str = "unknown") -> None: ...


class SearchDataStoreProtocol(Protocol):
    def search_with_data(
        self,
        query: str,
        plugin_data: list[JSONDict] | None,
        model_data: dict[str, list[JSONDict]] | None,
        hardware_data: JSONDict | None,
        limit: int = 5,
    ) -> dict[str, list[JSONDict]]: ...


class StateAggregatorProtocol(Protocol):
    @property
    def search_store(self) -> SearchDataStoreProtocol: ...

    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def get_plugin_status(self, plugin_name: str) -> PluginRuntimeStateName: ...

    async def apply_authoritative_plugin_state_change(
        self,
        event: PluginInstallationStateChangedEvent | PluginRuntimeStateChangedEvent,
    ) -> None: ...

    async def update_plugin_health_status(
        self,
        plugin_name: str,
        health_status: PluginHealthStatus,
    ) -> None: ...

    async def get_plugin_health_statuses(self) -> dict[str, PluginHealthStatus]: ...

    async def get_all_plugin_states(self) -> ImmutablePluginStates: ...

    async def get_main_state(self) -> dict[str, str]: ...

    async def get_state_version(self) -> int: ...

    async def get_all_plugin_states_with_version(
        self,
    ) -> tuple[ImmutablePluginStates, int]: ...

    async def clear_purged_status(self, plugin_name: str) -> None: ...

    async def set_main_state(self, new_state: SoAIMainState, reason: str) -> None: ...

    async def recalculate_and_set_main_state(self, reason: str) -> SoAIMainState | None: ...


class AuthoritativePluginStateTransitionsProtocol(Protocol):
    def bind_runtime_state_side_effects(
        self,
        runtime_state_side_effects: RuntimeStatePublicationSideEffectsProtocol,
    ) -> None: ...

    async def publish_runtime_state_change(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        *,
        details: JSONDict | None = None,
        expected_previous_state: PluginRuntimeStateName | None = None,
        prioritize_for_eviction: bool = False,
    ) -> AuthoritativePluginStateTransitionReceipt | None: ...

    async def begin_runtime_transition(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        *,
        context: RequestContext | None = None,
        details: JSONDict | None = None,
        expected_previous_state: PluginRuntimeStateName | None = None,
    ) -> AuthoritativePluginStateTransitionReceipt | None: ...

    async def begin_installation_transition(
        self,
        plugin_name: str,
        new_state: PluginRuntimeStateName,
        reason: str,
        *,
        context: RequestContext | None = None,
    ) -> AuthoritativePluginStateTransitionReceipt | None: ...
