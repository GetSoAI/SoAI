"""SoAI - Plugin manager dependency injection dataclasses [backend/plugins/manager/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import httpx2

from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.ttl_cache import TTLCache
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.files.file_identity import FileIdentity
from core.formatting.protocols import FormatBytesCallable
from core.hardware.protocols import (
    DatabaseHardwareProtocol,
    GetGpuInfoCallable,
    HardwareManagerProtocol,
)
from core.hardware.protocols_storage import StorageManagerProtocol
from core.ipc.protocols import ManagedIpcWorkerFactoryProtocol
from core.logging.protocols import LoggingManagerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import (
    ModelProviderCoordinatorProtocol,
    ModelRegistryProtocol,
    ParameterManagerProtocol,
)
from core.models.protocols_database import ModelDatabasePurgeServiceProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.logo_contract import PluginLogoResult
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
from core.plugins.protocols_manager_dependencies import PluginUpdaterProtocol
from core.plugins.protocols_manager_environment import PluginEnvironmentManagerProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.state.protocols import (
    AuthoritativePluginStateTransitionsProtocol,
    StateAggregatorProtocol,
)
from core.tasks.protocols import (
    CancellationTokenScopeCallable,
    CancelTaskCallable,
    SpawnTrackedTaskCallable,
    TaskRegistryProtocol,
)
from core.tasks.protocols_operations import (
    CreateStreamingTaskCallable,
    SendErrorEventCallable,
    SendTaskCompleteEventCallable,
    SendTaskProgressEventCallable,
)
from plugins.manager.policy import PluginManagerPolicy

__all__ = (
    "PluginManagerCoreDependencies",
    "PluginManagerDatabaseDependencies",
    "PluginManagerDependencies",
    "PluginManagerHardwareHelpers",
    "PluginManagerInfrastructureDependencies",
    "PluginManagerModelDependencies",
    "PluginManagerPaths",
    "PluginManagerTaskHelpers",
)


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerTaskHelpers:
    spawn_tracked_task: SpawnTrackedTaskCallable
    cancel_task: CancelTaskCallable
    cancellation_token_scope: CancellationTokenScopeCallable
    send_error_event: SendErrorEventCallable
    send_task_complete_event: SendTaskCompleteEventCallable
    send_task_progress_event: SendTaskProgressEventCallable
    create_streaming_task: CreateStreamingTaskCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerTaskHelpers",
            spawn_tracked_task=self.spawn_tracked_task,
            cancel_task=self.cancel_task,
            cancellation_token_scope=self.cancellation_token_scope,
            send_error_event=self.send_error_event,
            send_task_complete_event=self.send_task_complete_event,
            send_task_progress_event=self.send_task_progress_event,
            create_streaming_task=self.create_streaming_task,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerHardwareHelpers:
    get_gpu_info: GetGpuInfoCallable
    format_bytes: FormatBytesCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerHardwareHelpers",
            get_gpu_info=self.get_gpu_info,
            format_bytes=self.format_bytes,
        )


@dataclasses.dataclass(slots=True)
class PluginManagerPaths:
    plugin_directory: str
    backends_directory: str
    plugin_directory_real: str
    temp_directory: str
    plugin_venvs_root: str


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerCoreDependencies:
    config: ConfigProtocol
    files: FilesProtocol
    routing_config: RoutingConfig
    http_client: httpx2.AsyncClient
    log_manager: LoggingManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerCoreDependencies",
            config=self.config,
            files=self.files,
            http_client=self.http_client,
            log_manager=self.log_manager,
            routing_config=self.routing_config,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerInfrastructureDependencies:
    hw_manager: HardwareManagerProtocol
    storage_manager: StorageManagerProtocol
    event_bus: EventBusProtocol
    metrics_manager: MetricsManagerProtocol
    config_manager: ConfigManagerProtocol
    state_aggregator: StateAggregatorProtocol
    lifecycle_publisher: AuthoritativePluginStateTransitionsProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    lifecycle: PluginLifecycleProtocol
    task_registry: TaskRegistryProtocol
    task_helpers: PluginManagerTaskHelpers
    hardware_helpers: PluginManagerHardwareHelpers
    environment_manager: PluginEnvironmentManagerProtocol
    managed_ipc_worker_factory: ManagedIpcWorkerFactoryProtocol
    ipc_encoding_pool: BoundedBlockingPool
    logo_preparation_pool: BoundedBlockingPool
    logo_cache: TTLCache[tuple[str, FileIdentity], PluginLogoResult]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerInfrastructureDependencies",
            config_manager=self.config_manager,
            event_bus=self.event_bus,
            hardware_helpers=self.hardware_helpers,
            hw_manager=self.hw_manager,
            lifecycle=self.lifecycle,
            lifecycle_publisher=self.lifecycle_publisher,
            metrics_manager=self.metrics_manager,
            runtime_flags=self.runtime_flags,
            state_aggregator=self.state_aggregator,
            storage_manager=self.storage_manager,
            task_helpers=self.task_helpers,
            task_registry=self.task_registry,
            environment_manager=self.environment_manager,
            ipc_encoding_pool=self.ipc_encoding_pool,
            logo_preparation_pool=self.logo_preparation_pool,
            logo_cache=self.logo_cache,
            managed_ipc_worker_factory=self.managed_ipc_worker_factory,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerDatabaseDependencies:
    plugins: DatabasePluginsProtocol
    hardware: DatabaseHardwareProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerDatabaseDependencies",
            hardware=self.hardware,
            plugins=self.plugins,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerModelDependencies:
    parameter_manager: ParameterManagerProtocol
    model_registry: ModelRegistryProtocol
    model_database_purge_service: ModelDatabasePurgeServiceProtocol
    model_provider_coordinator: ModelProviderCoordinatorProtocol | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerModelDependencies",
            model_database_purge_service=self.model_database_purge_service,
            model_registry=self.model_registry,
            parameter_manager=self.parameter_manager,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class PluginManagerDependencies:
    core: PluginManagerCoreDependencies
    infrastructure: PluginManagerInfrastructureDependencies
    databases: PluginManagerDatabaseDependencies
    models: PluginManagerModelDependencies
    policy: PluginManagerPolicy
    plugin_directory: str
    backends_directory: str
    updater: PluginUpdaterProtocol
    plugin_path_resolver: Callable[[str, str], tuple[str, str, str]]
    transfer_flag_resolver: Callable[[ConfigProtocol], tuple[bool, bool, bool]]
    temp_directory_resolver: Callable[[FilesProtocol, ConfigProtocol], str]
    plugin_venvs_root_resolver: Callable[[FilesProtocol, ConfigProtocol], str]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginManagerDependencies",
            backends_directory=self.backends_directory,
            core=self.core,
            databases=self.databases,
            infrastructure=self.infrastructure,
            models=self.models,
            plugin_directory=self.plugin_directory,
            plugin_path_resolver=self.plugin_path_resolver,
            plugin_venvs_root_resolver=self.plugin_venvs_root_resolver,
            policy=self.policy,
            temp_directory_resolver=self.temp_directory_resolver,
            transfer_flag_resolver=self.transfer_flag_resolver,
            updater=self.updater,
        )
