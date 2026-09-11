"""SoAI - Plugin manager dependency protocols [backend/core/plugins/protocols_manager_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.models.protocols_database import ModelDatabasePurgeServiceProtocol

__all__ = (
    "PluginManagerCoreDependenciesProtocol",
    "PluginManagerDatabaseDependenciesProtocol",
    "PluginManagerDependenciesProtocol",
    "PluginManagerHardwareHelpersProtocol",
    "PluginManagerInfrastructureDependenciesProtocol",
    "PluginManagerModelDependenciesProtocol",
    "PluginManagerPathsProtocol",
    "PluginManagerStateProtocol",
    "PluginManagerTaskHelpersProtocol",
    "PluginUpdaterProtocol",
)


if TYPE_CHECKING:
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.concurrency.ttl_cache import TTLCache
    from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
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
    from core.orchestrator.routing_config import RoutingConfig
    from core.plugins.logo_contract import PluginLogoResult
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.plugins.protocols_instance import FilesProtocol
    from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
    from core.plugins.protocols_manager_environment import (
        PluginEnvironmentManagerProtocol,
    )
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
    from core.types.json import JSONDict
    from core.types.protocols import HttpClientProtocol


class PluginManagerStateProtocol(Protocol): ...


class PluginManagerTaskHelpersProtocol(Protocol):
    @property
    def spawn_tracked_task(self) -> SpawnTrackedTaskCallable: ...
    @property
    def cancel_task(self) -> CancelTaskCallable: ...
    @property
    def cancellation_token_scope(self) -> CancellationTokenScopeCallable: ...
    @property
    def send_error_event(self) -> SendErrorEventCallable: ...
    @property
    def send_task_complete_event(self) -> SendTaskCompleteEventCallable: ...
    @property
    def send_task_progress_event(self) -> SendTaskProgressEventCallable: ...
    @property
    def create_streaming_task(self) -> CreateStreamingTaskCallable: ...


class PluginManagerHardwareHelpersProtocol(Protocol):
    @property
    def get_gpu_info(self) -> GetGpuInfoCallable: ...
    @property
    def format_bytes(self) -> FormatBytesCallable: ...


class PluginManagerCoreDependenciesProtocol(Protocol):
    @property
    def config(self) -> ConfigProtocol: ...
    @property
    def files(self) -> FilesProtocol: ...
    @property
    def routing_config(self) -> RoutingConfig: ...
    @property
    def http_client(self) -> HttpClientProtocol: ...
    @property
    def log_manager(self) -> LoggingManagerProtocol: ...


class PluginManagerInfrastructureDependenciesProtocol(Protocol):
    @property
    def logo_preparation_pool(self) -> BoundedBlockingPool: ...
    @property
    def logo_cache(self) -> TTLCache[tuple[str, FileIdentity], PluginLogoResult]: ...
    @property
    def hw_manager(self) -> HardwareManagerProtocol: ...
    @property
    def storage_manager(self) -> StorageManagerProtocol: ...
    @property
    def event_bus(self) -> EventBusProtocol: ...
    @property
    def metrics_manager(self) -> MetricsManagerProtocol: ...
    @property
    def config_manager(self) -> ConfigManagerProtocol: ...
    @property
    def state_aggregator(self) -> StateAggregatorProtocol: ...
    @property
    def lifecycle_publisher(self) -> AuthoritativePluginStateTransitionsProtocol: ...
    @property
    def runtime_flags(self) -> RuntimeFlagsViewProtocol: ...
    @property
    def lifecycle(self) -> PluginLifecycleProtocol: ...
    @property
    def task_registry(self) -> TaskRegistryProtocol: ...
    @property
    def task_helpers(self) -> PluginManagerTaskHelpersProtocol: ...
    @property
    def hardware_helpers(self) -> PluginManagerHardwareHelpersProtocol: ...
    @property
    def environment_manager(self) -> PluginEnvironmentManagerProtocol: ...
    @property
    def managed_ipc_worker_factory(self) -> ManagedIpcWorkerFactoryProtocol: ...

    @property
    def ipc_encoding_pool(self) -> BoundedBlockingPool: ...


class PluginManagerDatabaseDependenciesProtocol(Protocol):
    @property
    def plugins(self) -> DatabasePluginsProtocol: ...
    @property
    def hardware(self) -> DatabaseHardwareProtocol: ...


class PluginManagerModelDependenciesProtocol(Protocol):
    @property
    def parameter_manager(self) -> ParameterManagerProtocol: ...
    @property
    def model_registry(self) -> ModelRegistryProtocol: ...
    @property
    def model_database_purge_service(self) -> ModelDatabasePurgeServiceProtocol: ...
    @property
    def model_provider_coordinator(self) -> ModelProviderCoordinatorProtocol | None: ...


class PluginManagerDependenciesProtocol(Protocol):
    @property
    def core(self) -> PluginManagerCoreDependenciesProtocol: ...
    @property
    def infrastructure(self) -> PluginManagerInfrastructureDependenciesProtocol: ...
    @property
    def databases(self) -> PluginManagerDatabaseDependenciesProtocol: ...
    @property
    def models(self) -> PluginManagerModelDependenciesProtocol: ...


class PluginManagerPathsProtocol(Protocol):
    plugin_directory: str
    backends_directory: str
    plugin_directory_real: str
    temp_directory: str
    plugin_venvs_root: str


class PluginUpdaterProtocol(Protocol):
    async def check_for_app_update(self) -> JSONDict: ...
