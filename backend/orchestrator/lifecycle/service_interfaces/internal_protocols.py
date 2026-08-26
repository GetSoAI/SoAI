"""SoAI - Orchestrator lifecycle service protocols [backend/orchestrator/lifecycle/service_interfaces/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

from core.events.types_base import Event
from core.events.types_models_model_events import ModelParametersRequireReloadEvent
from core.events.types_plugins import (
    ClearQuarantineCommand,
    PluginLoadedEvent,
    PluginPurgedEvent,
    PluginStoppedEvent,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
)
from core.events.types_system import ConfigReloadedEvent
from core.orchestrator.protocols_lifecycle import (
    OrchestratorCircuitBreakersProtocol,
    OrchestratorLifecyclePublisherProtocol,
    OrchestratorShutdownProtocol,
    OrchestratorWatchersProtocol,
)
from core.orchestrator.routing_config import RoutingConfig, VirtualModelConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.orchestrator.scheduler_work import SchedulerWorkItem
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.tasks.protocols import RecoveryQueuePurgeProtocol
from orchestrator.lifecycle.config_reload_result import PluginConfigReloadResult
from orchestrator.lifecycle.runtime_mutation_commands import RuntimeMutationStopRequest
from orchestrator.lifecycle.state_access.internal_protocols import (
    PluginWorkPurgeProtocol,
)

if TYPE_CHECKING:
    from core.orchestrator.protocols_lifecycle import PluginStateProtocol
    from core.state.protocols import ImmutablePluginStates
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue
    from orchestrator.lifecycle.model_loading_result import ModelLoadingResult

__all__ = (
    "OrchestratorLifecycleCoordinatorProtocol",
    "OrchestratorLifecycleModelLoadingProtocol",
    "OrchestratorLifecycleRecoveryProtocol",
    "OrchestratorLifecycleRoutingConfigProtocol",
    "OrchestratorLifecycleRuntimeMutationsProtocol",
    "OrchestratorLifecycleShutdownCoordinatorProtocol",
    "OrchestratorLifecycleStartupProtocol",
    "OrchestratorLifecycleTaskTrackingProtocol",
    "OrchestratorLifecycleUserCommandsProtocol",
    "OrchestratorLifecycleWatchersProtocol",
)


class OrchestratorLifecycleTaskTrackingProtocol(Protocol):
    async def try_register_compatible_task_start(
        self,
        plugin_name: str,
        tracking_id: str,
        request_universal_id: str,
        request_startup_params: JSONDict,
        *,
        provider_backed: bool,
        persistent_runtime: bool,
    ) -> bool: ...

    async def register_task_finish(
        self,
        plugin_name: str,
        tracking_id: str,
        *,
        duration: float | None,
        completed: bool,
        cancelled: bool,
        is_persistent: bool,
        last_task_id: str | None,
    ) -> None: ...

    async def get_active_task_count(self, plugin_name: str) -> int: ...
    async def reload_params_match(
        self,
        plugin_name: str,
        loaded_params: JSONDict | None,
        request_params: JSONDict,
    ) -> bool: ...
    async def find_eviction_candidate(
        self,
        plugin_persistence: dict[str, bool],
        *,
        exclude: set[str] | None = None,
        all_states: ImmutablePluginStates | None = None,
        idle_plugins_snapshot: list[str] | None = None,
        plugin_states_snapshot: dict[str, PluginStateProtocol] | None = None,
        queue_empty_snapshot: dict[str, bool] | None = None,
    ) -> str | None: ...
    async def finalize_idle_state(
        self,
        plugin_name: str,
        *,
        last_task_id: str | None = None,
        cancelled: bool = False,
        is_persistent_override: bool | None = None,
    ) -> None: ...
    async def log_task_configuration(
        self,
        task: Task,
        model_info: dict[str, JSONValue],
    ) -> None: ...


class OrchestratorLifecycleStartupProtocol(Protocol):
    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None: ...

    async def execute_plugin_config_reload(
        self,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult: ...
    async def publish_config_reload_failure(
        self,
        event: ConfigReloadedEvent,
        error: str,
    ) -> None: ...
    async def handle_plugin_config_reloaded(
        self,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult: ...
    async def handle_parameters_changed(
        self,
        event: ModelParametersRequireReloadEvent,
    ) -> list[SchedulerWorkItem]: ...
    async def load_virtual_models(self) -> None: ...
    async def get_virtual_model_map(self) -> dict[str, VirtualModelConfig]: ...


class OrchestratorLifecycleRoutingConfigProtocol(Protocol):
    async def apply_core_routing_config_update(
        self,
        event: ConfigReloadedEvent,
    ) -> str | None: ...
    async def handle_get_routing_config(self, event: Event) -> None: ...
    async def handle_update_routing_config(self, event: Event) -> None: ...


class OrchestratorLifecycleWatchersProtocol(OrchestratorWatchersProtocol, Protocol):
    def bind_runtime_mutations(
        self,
        runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol,
    ) -> None: ...

    async def handle_state_change(self, event: Event) -> None: ...
    async def handle_plugin_stopped(self, event: PluginStoppedEvent) -> list[SchedulerWorkItem]: ...
    async def handle_plugin_reloaded(self, event: PluginLoadedEvent) -> None: ...
    async def handle_plugin_purged(self, event: PluginPurgedEvent) -> None: ...


class OrchestratorLifecycleUserCommandsProtocol(Protocol):
    def bind_plugin_work_purge(
        self,
        purge_plugin_requests: PluginWorkPurgeProtocol,
    ) -> None: ...
    async def handle_clear_quarantine(
        self,
        event: ClearQuarantineCommand,
    ) -> list[SchedulerWorkItem]: ...
    async def handle_plugin_stop_command(
        self,
        command: RequestPluginStopAndWaitCommand,
    ) -> None: ...
    async def handle_plugin_disable_command(self, command: RequestPluginDisableCommand) -> None: ...
    async def handle_plugin_enable_command(
        self,
        command: RequestPluginEnableCommand,
    ) -> list[SchedulerWorkItem]: ...


class OrchestratorLifecycleRuntimeMutationsProtocol(Protocol):
    async def start(self) -> None: ...
    async def submit_config_reload(
        self,
        event: ConfigReloadedEvent,
    ) -> PluginConfigReloadResult: ...
    async def submit_stop_plugin(
        self,
        request: RuntimeMutationStopRequest,
    ) -> PluginStopOutcome: ...
    async def submit_stop_command(self, command: RequestPluginStopAndWaitCommand) -> None: ...
    async def submit_disable_command(self, command: RequestPluginDisableCommand) -> None: ...
    async def submit_enable_command(
        self,
        command: RequestPluginEnableCommand,
    ) -> list[SchedulerWorkItem]: ...
    async def submit_clear_quarantine_command(
        self,
        command: ClearQuarantineCommand,
    ) -> list[SchedulerWorkItem]: ...
    async def submit_recovery(self, plugin_name: str, reason: str) -> None: ...
    async def discard_plugin(self, plugin_name: str) -> None: ...
    async def shutdown(self, timeout_seconds: float) -> None: ...


class OrchestratorLifecycleShutdownCoordinatorProtocol(OrchestratorShutdownProtocol, Protocol):
    async def wait_for_active_tasks_to_drain(self, plugin_name: str) -> str | None: ...
    async def perform_plugin_stop_logic(self, plugin_name: str) -> PluginStopOutcome: ...
    async def stop_plugin_for_shutdown(
        self,
        plugin_name: str,
        *,
        reason: str,
        stop_timeout_sec: float,
    ) -> PluginStopOutcome: ...


class OrchestratorLifecycleRecoveryProtocol(Protocol):
    def update_config(self, max_recovery_attempts: int) -> None: ...
    def bind_queue_purge(self, purge_callback: RecoveryQueuePurgeProtocol) -> None: ...
    async def purge_plugin_tasks(self, plugin_name: str, reason: str) -> None: ...
    async def handle_plugin_recovery(self, plugin_name: str, reason: str) -> None: ...


class OrchestratorLifecycleModelLoadingProtocol(Protocol):
    def update_config(self, health_check_config: JSONDict) -> None: ...
    async def start_plugin_and_load_model(
        self,
        task: Task,
        plugin_name: str,
        model_info: Mapping[str, JSONValue],
    ) -> ModelLoadingResult: ...


class OrchestratorLifecycleCoordinatorProtocol(Protocol):
    @property
    def routing_config(self) -> RoutingConfig: ...

    @routing_config.setter
    def routing_config(self, value: RoutingConfig) -> None: ...

    startup: OrchestratorLifecycleStartupProtocol
    routing: OrchestratorLifecycleRoutingConfigProtocol
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol
    watchers: OrchestratorLifecycleWatchersProtocol
    publisher: OrchestratorLifecyclePublisherProtocol
    circuit_breakers: OrchestratorCircuitBreakersProtocol
    task_tracking: OrchestratorLifecycleTaskTrackingProtocol
    user_commands: OrchestratorLifecycleUserCommandsProtocol
    recovery: OrchestratorLifecycleRecoveryProtocol
    model_loading: OrchestratorLifecycleModelLoadingProtocol
    runtime_mutations: OrchestratorLifecycleRuntimeMutationsProtocol

    async def update_config(self, config: OrchestratorRuntimeConfig) -> None: ...
