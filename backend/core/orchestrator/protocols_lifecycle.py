"""SoAI - Orchestrator lifecycle and control protocol contracts [backend/core/orchestrator/protocols_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from core.events.types_base import Event
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.runtime.request_context import RequestContext
from core.runtime.request_sources import RequestSource
from core.state.protocols import (
    AuthoritativePluginStateTransitionReceipt,
)
from core.state.state_names import PluginRuntimeStateName
from core.tasks.type_catalog import TaskTypeId

if TYPE_CHECKING:
    from typing import Literal

    from core.events.types_models_requests import InferenceRequestReceived
    from core.events.types_system import ConfigReloadedEvent
    from core.state.health_status import PluginHealthStatus
    from core.state.plugin_state_generation import PluginStateGeneration
    from core.tasks.task import Task
    from core.types.json import JSONDict

    type InferenceDeliveryMode = Literal["async", "blocking", "streaming"]

__all__ = (
    "CoreRoutingConfigApplicatorProtocol",
    "InferenceAdmissionReceipt",
    "InferenceAdmissionRequest",
    "OrchestratorCircuitBreakersProtocol",
    "OrchestratorControlProtocol",
    "OrchestratorLifecycleProtocol",
    "OrchestratorLifecyclePublisherProtocol",
    "OrchestratorRecoveryProtocol",
    "OrchestratorRoutingProtocol",
    "OrchestratorShutdownProtocol",
    "OrchestratorWatchersProtocol",
    "PluginStateProtocol",
)


@dataclass(frozen=True, slots=True)
class InferenceAdmissionRequest:
    request_context: RequestContext
    payload: JSONDict
    task_type: TaskTypeId
    user_id: int
    owner_type: str
    owner_id: str
    cancellation_id: str
    metadata: JSONDict
    request_event_class: type[InferenceRequestReceived]
    request_source: RequestSource
    delivery_mode: InferenceDeliveryMode
    required_capabilities: tuple[str, ...] = ()
    required_modalities: tuple[str, ...] = ()
    task_id: str | None = None
    reply_queue: asyncio.Queue[Event] | None = None
    attach_reply_queue: bool = True
    reply_queue_maxsize: int = 1000


@dataclass(frozen=True, slots=True)
class InferenceAdmissionReceipt:
    task: Task
    reply_queue: asyncio.Queue[Event] | None


class OrchestratorControlProtocol(Protocol):
    async def start(self) -> None: ...

    def set_quiescent(self, value: bool) -> None: ...

    def is_quiescent(self) -> bool: ...

    async def get_status(self) -> JSONDict: ...

    async def accept_inference_request(
        self,
        request: InferenceAdmissionRequest,
    ) -> InferenceAdmissionReceipt: ...

    async def shutdown(self) -> None: ...


class PluginStateProtocol(Protocol):
    plugin_name: str
    loaded_model_universal_id: str | None
    last_request_universal_id: str | None
    loaded_parameters: JSONDict | None
    parameter_version: int | None
    last_activity: float
    is_busy: bool
    active_tasks: set[str]
    avg_processing_time_ema: float
    model_load_time: float | None
    finalize_pending: bool


class OrchestratorWatchersProtocol(Protocol):
    async def get_idle_plugins_snapshot(self) -> list[str]: ...

    async def get_idle_plugins_with_timestamps(self) -> list[tuple[str, float]]: ...

    async def reconcile_idle_plugins(self, *, add: dict[str, float], remove: set[str]) -> None: ...

    async def set_plugin_health_status(
        self,
        plugin_name: str,
        health: PluginHealthStatus,
    ) -> None: ...

    async def clear_plugin_recovery_attempts(self, plugin_name: str) -> None: ...

    async def get_plugin_states_snapshot(
        self,
        plugin_names: set[str] | None = None,
    ) -> dict[str, PluginStateProtocol]: ...

    async def get_plugin_state(self, plugin_name: str) -> PluginStateProtocol | None: ...

    async def get_status_snapshot(self) -> JSONDict: ...


class OrchestratorLifecyclePublisherProtocol(Protocol):
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


class OrchestratorCircuitBreakersProtocol(Protocol):
    async def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...

    async def load_circuit_breakers(self) -> None: ...

    async def persist_dirty_states_loop(self) -> None: ...

    async def flush_dirty_breakers(self) -> None: ...

    async def get_all_circuit_breaker_snapshots(self) -> dict[str, JSONDict]: ...

    async def get_circuit_breaker_snapshot(self, plugin_name: str) -> JSONDict: ...

    async def is_circuit_breaker_open(self, plugin_name: str) -> bool: ...

    async def allow_circuit_breaker_request(self, plugin_name: str) -> bool: ...

    async def record_cb_failure(self, plugin_name: str) -> None: ...

    async def record_cb_success(self, plugin_name: str) -> None: ...

    async def trip_circuit_breaker(self, plugin_name: str) -> None: ...


class OrchestratorRecoveryProtocol(Protocol):
    def update_config(self, max_recovery_attempts: int) -> None: ...

    async def purge_plugin_tasks(self, plugin_name: str, reason: str) -> None: ...

    async def handle_plugin_recovery(
        self,
        plugin_name: str,
        reason: str,
        *,
        expected_generation: PluginStateGeneration | None = None,
    ) -> None: ...


class OrchestratorShutdownProtocol(Protocol):
    def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...

    async def stop_plugin(
        self,
        plugin_name: str,
        *,
        reason: str = "Plugin stop requested",
        reply_channel: asyncio.Queue[Event] | None = None,
        publish_state_changes: bool = True,
        wait_for_state_changes: bool = True,
        force: bool = False,
        stop_timeout_sec: float | None = None,
    ) -> PluginStopOutcome: ...


class OrchestratorRoutingProtocol(Protocol):
    async def apply_core_routing_config_update(self, event: ConfigReloadedEvent) -> str | None: ...

    async def handle_get_routing_config(self, event: Event) -> None: ...

    async def handle_update_routing_config(self, event: Event) -> None: ...


class OrchestratorLifecycleProtocol(Protocol):
    @property
    def routing_config(self) -> RoutingConfig: ...

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None: ...

    @property
    def routing(self) -> OrchestratorRoutingProtocol: ...

    @property
    def watchers(self) -> OrchestratorWatchersProtocol: ...

    @property
    def publisher(self) -> OrchestratorLifecyclePublisherProtocol: ...

    @property
    def circuit_breakers(self) -> OrchestratorCircuitBreakersProtocol: ...

    @property
    def recovery(self) -> OrchestratorRecoveryProtocol: ...

    @property
    def shutdown(self) -> OrchestratorShutdownProtocol: ...

    async def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...


class CoreRoutingConfigApplicatorProtocol(Protocol):
    async def apply_core_routing_config_update(self, event: ConfigReloadedEvent) -> str | None: ...
