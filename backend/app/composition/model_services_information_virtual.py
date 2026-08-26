"""SoAI - Model information service and virtual model coordinator assembly [backend/app/composition/model_services_information_virtual.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.concurrency.ttl_cache import TTLCache
from core.events.protocols import EventBusProtocol
from core.models.protocols import (
    ModelRegistryProtocol,
    ParameterManagerProtocol,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import RoutingConfigHolder
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.protocols import StateAggregatorProtocol
from models.information.dependencies import ModelInformationServiceDependencies
from models.information.service import ModelInformationService
from models.routing import ModelRoutingPublisher, ModelRoutingPublisherDependencies
from models.virtual.coordinator import (
    VirtualModelCoordinator,
    VirtualModelCoordinatorDependencies,
)

__all__ = ("build_model_information_and_virtual_coordinator",)


def build_model_information_and_virtual_coordinator(
    *,
    database_models: DatabaseModelsProtocol,
    database_plugins: DatabasePluginsProtocol,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    model_registry: ModelRegistryProtocol,
    parameter_manager: ParameterManagerProtocol,
    installed_plugin_names_ref: Callable[[], set[str]],
    event_bus: EventBusProtocol,
    routing_config_holder: RoutingConfigHolder,
    resolution_cache_lock: asyncio.Lock,
    resolution_cache: TTLCache[str, str],
) -> tuple[ModelInformationService, VirtualModelCoordinator]:
    model_information_service = ModelInformationService(
        ModelInformationServiceDependencies(
            database_models=database_models,
            database_plugins=database_plugins,
            plugin_manager=plugin_manager,
            state_aggregator=state_aggregator,
            model_registry=model_registry,
            param_manager=parameter_manager,
            routing_config_holder=routing_config_holder,
            installed_plugin_names_ref=installed_plugin_names_ref,
        ),
    )
    routing_publisher = ModelRoutingPublisher(
        ModelRoutingPublisherDependencies(
            bus=event_bus,
            routing_config_holder=routing_config_holder,
            virtual_model_get_all=database_models.list_all_virtual_models,
        ),
    )
    virtual_model_coordinator = VirtualModelCoordinator(
        VirtualModelCoordinatorDependencies(
            database=database_models,
            publish=routing_publisher.publish,
            resolution_cache_lock=resolution_cache_lock,
            resolution_cache=resolution_cache,
        ),
    )
    return model_information_service, virtual_model_coordinator
