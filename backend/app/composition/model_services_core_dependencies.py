"""SoAI - Model services core dependency bundle [backend/app/composition/model_services_core_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.internal_protocols import LifecycleCoordinatorProtocol
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import (
    ModelRegistryProtocol,
    ParameterManagerProtocol,
)
from core.models.protocols_database import (
    DatabaseModelsProtocol,
    ModelDatabasePurgeServiceProtocol,
)
from core.orchestrator.routing_config import RoutingConfig, RoutingConfigHolder
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)

__all__ = ("ModelServicesCoreDependencies",)


@dataclass(frozen=True, slots=True)
class ModelServicesCoreDependencies:
    config: ConfigProtocol
    routing_config: RoutingConfig
    routing_config_holder: RoutingConfigHolder
    event_bus: EventBusProtocol
    domain_event_delivery: DurableEventDeliveryProtocol
    metrics_manager: MetricsManagerProtocol
    state_aggregator: StateAggregatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    task_registry: TaskRegistryProtocol
    database_models: DatabaseModelsProtocol
    database_plugins: DatabasePluginsProtocol
    plugin_manager: PluginManagerProtocol
    parameter_manager: ParameterManagerProtocol
    model_registry: ModelRegistryProtocol
    model_database_purge_service: ModelDatabasePurgeServiceProtocol
    model_record_locks: AsyncLockRegistryProtocol[str]
    lifecycle_coordinator: LifecycleCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelServicesCoreDependencies",
            config=self.config,
            routing_config=self.routing_config,
            routing_config_holder=self.routing_config_holder,
            event_bus=self.event_bus,
            domain_event_delivery=self.domain_event_delivery,
            metrics_manager=self.metrics_manager,
            state_aggregator=self.state_aggregator,
            token_collection=self.token_collection,
            task_registry=self.task_registry,
            cancellation_history=self.cancellation_history,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            database_models=self.database_models,
            database_plugins=self.database_plugins,
            plugin_manager=self.plugin_manager,
            parameter_manager=self.parameter_manager,
            model_registry=self.model_registry,
            model_database_purge_service=self.model_database_purge_service,
            model_record_locks=self.model_record_locks,
            lifecycle_coordinator=self.lifecycle_coordinator,
        )
