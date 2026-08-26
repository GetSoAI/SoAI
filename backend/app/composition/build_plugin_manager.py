"""SoAI - Plugin manager composition for application assembly [backend/app/composition/build_plugin_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import httpx2

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.composition.plugin_worker_support import build_plugin_worker_support
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.updater.release_fetch import fetch_latest_release_async
from core.concurrency.bounded_blocking import (
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
)
from core.concurrency.singleflight import SyncSingleflight
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.files.operations import ensure_dirs_exist
from core.formatting.bytes import format_bytes
from core.hardware.protocols import (
    DatabaseHardwareProtocol,
    GetGpuInfoCallable,
    HardwareManagerProtocol,
    NvmlGateProtocol,
)
from core.hardware.protocols_storage import StorageManagerProtocol
from core.logging.protocols import LoggingManagerProtocol
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import (
    ModelProviderCoordinatorProtocol,
    ModelRegistryProtocol,
    ParameterManagerProtocol,
)
from core.models.protocols_database import ModelDatabasePurgeServiceProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.state.protocols import (
    AuthoritativePluginStateTransitionsProtocol,
    StateAggregatorProtocol,
)
from core.system.protocols import CommandExecutorProtocol
from core.tasks.api_events import send_task_complete_event, send_task_progress_event
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.constants import PLUGIN_TASK_TTL_MS, PLUGIN_TASK_TYPE_PAIRS
from core.tasks.creation import create, create_streaming_task
from core.tasks.failure_events import send_error_event
from core.tasks.finalization import finalize
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from core.tasks.service_lifecycle import ServiceLifecycle, ServiceLifecycleDependencies
from core.tasks.status_transitions import update_status
from core.tasks.task_cancellation import cancel
from core.tasks.task_cancellation_ops import cancel_task
from hardware.gpu_info_cache_service import (
    GPUInfoCacheService,
    GPUInfoCacheServiceDependencies,
)
from hardware.info_gpu import get_gpu_info
from hardware.vendor_detection_service import (
    GPUVendorDetectionService,
    GPUVendorDetectionServiceDependencies,
)
from hardware.vendors.nvidia.persistence import (
    NvidiaCapabilitiesCacheService,
    NvidiaCapabilitiesCacheServiceDependencies,
)
from plugins.lifecycle import PluginLifecycle
from plugins.lifecycle_dependencies import PluginLifecycleDependencies
from plugins.manager.dependencies import (
    PluginManagerCoreDependencies,
    PluginManagerDatabaseDependencies,
    PluginManagerDependencies,
    PluginManagerHardwareHelpers,
    PluginManagerInfrastructureDependencies,
    PluginManagerModelDependencies,
    PluginManagerTaskHelpers,
)
from plugins.manager.lifecycle_startup import (
    PluginManagerStartupLifecycle,
    PluginManagerStartupLifecycleDependencies,
)
from plugins.manager.manager import PluginManager
from plugins.manager.policy import build_plugin_manager_policy
from plugins.state.transfer_resolvers import (
    default_plugin_path_resolver,
    default_plugin_venvs_root_resolver,
    default_temp_directory_resolver,
    default_transfer_flag_resolver,
)
from plugins.state.updater import build_updater_factory

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_plugin_manager",)

LOGGER_NAME_PLUGIN_MANAGER = "SoAI.app.composition.plugin_manager"
LOGGER_NAME_PLUGIN_MANAGER_HARDWARE = "SoAI.app.composition.plugin_manager_hardware"


def _create_get_gpu_info_callable(
    command_executor: CommandExecutorProtocol | None,
    nvidia_nvml_gate: NvmlGateProtocol,
) -> GetGpuInfoCallable:
    if command_executor is not None:
        logger = get_logger(LOGGER_NAME_PLUGIN_MANAGER_HARDWARE)
        gpu_info_cache_service = GPUInfoCacheService(GPUInfoCacheServiceDependencies())
        gpu_vendor_detection_service = GPUVendorDetectionService(
            GPUVendorDetectionServiceDependencies(logger=logger, command_executor=command_executor),
        )
        nvidia_capabilities_cache_service = NvidiaCapabilitiesCacheService(
            NvidiaCapabilitiesCacheServiceDependencies(
                entries={},
                entries_lock=threading.Lock(),
                singleflight=SyncSingleflight(),
            ),
        )

        def _enabled_get_gpu_info(detailed: bool = True) -> JSONDict:
            return get_gpu_info(
                command_executor,
                detailed=detailed,
                cache_service=gpu_info_cache_service,
                vendor_detection_service=gpu_vendor_detection_service,
                nvidia_nvml_gate=nvidia_nvml_gate,
                nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
            )

        return _enabled_get_gpu_info

    def _disabled_hardware_get_gpu_info(detailed: bool = True) -> JSONDict:
        _ = detailed
        return {"gpus": [], "compute_drivers": {}}

    return _disabled_hardware_get_gpu_info


async def build_plugin_manager(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    routing_config: RoutingConfig,
    http_client: httpx2.AsyncClient,
    log_manager: LoggingManagerProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    hardware_manager: HardwareManagerProtocol,
    storage_manager: StorageManagerProtocol,
    event_bus: EventBusProtocol,
    metrics_manager: MetricsManagerProtocol,
    config_manager: ConfigManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    authoritative_plugin_state_transitions: AuthoritativePluginStateTransitionsProtocol,
    cancellation_coordinator: CancellationCoordinatorProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    task_registry: TaskRegistryProtocol,
    task_registry_queries: TaskRegistryQueryView,
    database_plugins: DatabasePluginsProtocol,
    database_hardware: DatabaseHardwareProtocol,
    parameter_manager: ParameterManagerProtocol,
    model_registry: ModelRegistryProtocol,
    model_database_purge_service: ModelDatabasePurgeServiceProtocol,
    model_provider_coordinator: ModelProviderCoordinatorProtocol,
    plugin_directory: str,
    backends_directory: str,
    updater_module_dependencies: ApplicationUpdaterModuleDependencies,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    command_executor: CommandExecutorProtocol | None,
) -> PluginManager:
    await ensure_dirs_exist([backends_directory])
    plugin_manager_lifecycle = ServiceLifecycle(
        ServiceLifecycleDependencies(
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
        ),
    )
    updater_factory = build_updater_factory(
        module_dependencies_type=ApplicationUpdaterModuleDependencies,
        fetch_latest_release_async=fetch_latest_release_async,
    )
    updater = updater_factory(config, http_client, updater_module_dependencies)
    plugin_worker_support = build_plugin_worker_support(
        files=files,
        config=config,
        storage_manager=storage_manager,
        runtime_flags=runtime_flags,
    )
    ipc_encoding_pool = create_bounded_thread_pool_from_env(
        BoundedThreadPoolConfig(
            label="ipc-message-encoding",
            thread_name_prefix="soai-ipc-encode",
            max_workers_env="SOAI_IPC_ENCODING_MAX_WORKERS",
            max_in_flight_env="SOAI_IPC_ENCODING_MAX_IN_FLIGHT",
            default_max_workers=2,
            minimum_workers=1,
            maximum_workers=4,
            default_in_flight_multiplier=2,
            default_min_in_flight=4,
            max_in_flight_limit=16,
        ),
    )
    plugin_manager_dependencies = PluginManagerDependencies(
        core=PluginManagerCoreDependencies(
            config=config,
            files=files,
            routing_config=routing_config,
            http_client=http_client,
            log_manager=log_manager,
        ),
        infrastructure=PluginManagerInfrastructureDependencies(
            hw_manager=hardware_manager,
            storage_manager=storage_manager,
            event_bus=event_bus,
            metrics_manager=metrics_manager,
            config_manager=config_manager,
            state_aggregator=state_aggregator,
            lifecycle_publisher=authoritative_plugin_state_transitions,
            runtime_flags=runtime_flags,
            lifecycle=PluginLifecycle(
                PluginLifecycleDependencies(
                    lifecycle=plugin_manager_lifecycle,
                    locks=plugin_worker_support.lifecycle_locks,
                    cancellation_coordinator=cancellation_coordinator,
                    cancellation_history=cancellation_history,
                    cancellation_event_bus=cancellation_event_bus,
                    token_collection=token_collection,
                    cancellation_binder=cancellation_binder,
                    task_registry=task_registry,
                    task_registry_queries=task_registry_queries,
                    create_managed_task=spawn_tracked_task,
                    task_create=create,
                    task_cancel=cancel,
                    task_finalize=finalize,
                    task_update_status=update_status,
                    plugin_task_ttl_ms=PLUGIN_TASK_TTL_MS,
                    plugin_task_type_map=dict(PLUGIN_TASK_TYPE_PAIRS),
                ),
            ),
            task_registry=task_registry,
            task_helpers=PluginManagerTaskHelpers(
                spawn_tracked_task=spawn_tracked_task,
                cancel_task=cancel_task,
                cancellation_token_scope=cancellation_token_scope,
                send_error_event=send_error_event,
                send_task_complete_event=send_task_complete_event,
                send_task_progress_event=send_task_progress_event,
                create_streaming_task=create_streaming_task,
            ),
            hardware_helpers=PluginManagerHardwareHelpers(
                get_gpu_info=_create_get_gpu_info_callable(
                    command_executor,
                    hardware_manager.nvidia_nvml_gate,
                ),
                format_bytes=format_bytes,
            ),
            environment_manager=plugin_worker_support.environment_manager,
            ipc_encoding_pool=ipc_encoding_pool,
            managed_ipc_worker_factory=plugin_worker_support.managed_ipc_worker_factory,
        ),
        databases=PluginManagerDatabaseDependencies(
            plugins=database_plugins,
            hardware=database_hardware,
        ),
        models=PluginManagerModelDependencies(
            parameter_manager=parameter_manager,
            model_registry=model_registry,
            model_database_purge_service=model_database_purge_service,
            model_provider_coordinator=model_provider_coordinator,
        ),
        policy=build_plugin_manager_policy(),
        plugin_directory=plugin_directory,
        backends_directory=backends_directory,
        updater=updater,
        plugin_path_resolver=default_plugin_path_resolver,
        transfer_flag_resolver=default_transfer_flag_resolver,
        temp_directory_resolver=default_temp_directory_resolver,
        plugin_venvs_root_resolver=default_plugin_venvs_root_resolver,
    )
    plugin_manager = PluginManager(deps=plugin_manager_dependencies)
    plugin_manager_lifecycle_controller = plugin_manager.lifecycle_controller
    plugin_manager_lifecycle_controller.attach_startup_lifecycle(
        PluginManagerStartupLifecycle(
            PluginManagerStartupLifecycleDependencies(
                manager=plugin_manager,
                command_map=plugin_manager_lifecycle_controller.command_map,
                controller=plugin_manager_lifecycle_controller,
            ),
        ),
    )
    lifecycle_coordinator.register_actor(plugin_manager)
    get_logger(LOGGER_NAME_PLUGIN_MANAGER).debug(
        "PluginManager initialized with %s backends directory",
        backends_directory,
    )
    return plugin_manager
