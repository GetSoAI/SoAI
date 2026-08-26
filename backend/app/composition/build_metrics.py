"""SoAI - Metrics subsystem composition helpers [backend/app/composition/build_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.internal_protocols import (
    MetricsAwareDatabaseCoreProtocol,
    MetricsAwareEventBusProtocol,
)
from app.lifecycle.coordinator import LifecycleCoordinator
from core.concurrency.bounded_blocking import (
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
)
from core.config.protocols import ConfigProtocol
from core.hardware.protocols import DatabaseHardwareProtocol
from core.logging.trace import get_logger
from core.metrics.protocols import DatabaseMetricsProtocol
from core.openai.prompt_counting_runtime import (
    PromptCountingRuntime,
    PromptCountingRuntimeDependencies,
)
from core.openai.token_counter import PromptTokenCounter
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.service_lifecycle import ServiceLifecycle, ServiceLifecycleDependencies
from hardware.storage.dependencies import StorageManagerDependencies
from hardware.storage.manager import StorageManager
from metrics.manager.dependencies import MetricsManagerDependencies
from metrics.manager.service import MetricsManager
from orchestrator.state.aggregator import StateAggregator
from orchestrator.state.dependencies import (
    MainStateControllerDependencies,
    PluginStateStoreDependencies,
    StateAggregatorDependencies,
)
from orchestrator.state.main_state_controller import MainStateController
from orchestrator.state.plugin_state_store import PluginStateStore

__all__ = ("build_metrics_and_state_services",)

LOGGER_NAME = "SoAI.app.composition.build_metrics"


def build_metrics_and_state_services(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    base_dir: str,
    event_bus: MetricsAwareEventBusProtocol,
    database_writer: MetricsAwareDatabaseCoreProtocol,
    database_metrics: DatabaseMetricsProtocol,
    database_hardware: DatabaseHardwareProtocol,
    database_plugins: DatabasePluginsProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    lifecycle_coordinator: LifecycleCoordinator,
) -> tuple[MetricsManager, StateAggregator, StorageManager, PromptTokenCounter]:
    metrics_lifecycle = ServiceLifecycle(
        ServiceLifecycleDependencies(
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            managed_task_group_label="metrics manager periodic tasks",
            managed_task_group_logger=get_logger(LOGGER_NAME),
        ),
    )
    metrics_manager = MetricsManager(
        MetricsManagerDependencies(
            config=config,
            database_metrics=database_metrics,
            database_hardware=database_hardware,
            database_plugins=database_plugins,
            lifecycle=metrics_lifecycle,
            event_bus=event_bus,
        ),
    )
    prompt_counting_pool = create_bounded_thread_pool_from_env(
        BoundedThreadPoolConfig(
            label="prompt-token-counting",
            thread_name_prefix="soai-token-count",
            max_workers_env="SOAI_TOKEN_COUNTING_MAX_WORKERS",
            max_in_flight_env="SOAI_TOKEN_COUNTING_MAX_IN_FLIGHT",
            default_max_workers=2,
            minimum_workers=1,
            maximum_workers=4,
            default_in_flight_multiplier=2,
            default_min_in_flight=4,
            max_in_flight_limit=16,
        ),
    )
    prompt_token_counter = PromptTokenCounter(
        runtime=PromptCountingRuntime(
            PromptCountingRuntimeDependencies(blocking_pool=prompt_counting_pool),
        ),
    )
    event_bus.set_metrics_recorder(metrics_manager)
    database_writer.set_metrics_recorder(metrics_manager)
    lifecycle_coordinator.register_actor(metrics_manager)
    state_aggregator = StateAggregator(
        StateAggregatorDependencies(
            event_bus=event_bus,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            plugin_store=PluginStateStore(
                PluginStateStoreDependencies(database_plugins=database_plugins),
            ),
            main_state_controller=MainStateController(
                MainStateControllerDependencies(
                    event_bus=event_bus,
                    cancellation_binder=cancellation_binder,
                    finalizer_tracker=finalizer_tracker,
                ),
            ),
        ),
    )
    storage_manager = StorageManager(
        StorageManagerDependencies(
            config=config,
            files=files,
            base_dir=base_dir,
        ),
    )
    return (
        metrics_manager,
        state_aggregator,
        storage_manager,
        prompt_token_counter,
    )
