"""SoAI - Model manager dependency bundle [backend/models/manager/coordinator/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
from core.models.protocols import (
    ModelDiscoveryServiceProtocol,
    ModelInformationServiceProtocol,
    ModelRegistryProtocol,
    ModelResolutionServiceProtocol,
    ParameterManagerProtocol,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.plugins.protocols import PluginManagerProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from models.internal_protocols import (
    AsyncParameterCacheProtocol,
    ModelActionsServiceProtocol,
    ModelParameterMutationServiceProtocol,
)

__all__ = ("ModelManagerDependencies",)


@dataclass(frozen=True, slots=True)
class ModelManagerDependencies:
    config: ConfigProtocol
    event_bus: EventBusProtocol
    domain_event_delivery: DurableEventDeliveryProtocol
    plugin_manager: PluginManagerProtocol
    database_models: DatabaseModelsProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    task_registry: TaskRegistryProtocol
    shutdown_event: asyncio.Event
    model_services_ready_event: asyncio.Event
    model_discovery_service: ModelDiscoveryServiceProtocol
    model_actions_service: ModelActionsServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_parameter_mutations: ModelParameterMutationServiceProtocol
    model_parameter_cache: AsyncParameterCacheProtocol
    model_parameter_manager: ParameterManagerProtocol
    model_registry: ModelRegistryProtocol
    installed_plugin_names_ref: Callable[[], set[str]]
    set_installed_plugin_names: Callable[[set[str]], None]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelManagerDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            database_models=self.database_models,
            event_bus=self.event_bus,
            domain_event_delivery=self.domain_event_delivery,
            finalizer_tracker=self.finalizer_tracker,
            installed_plugin_names_ref=self.installed_plugin_names_ref,
            model_actions_service=self.model_actions_service,
            model_discovery_service=self.model_discovery_service,
            model_information_service=self.model_information_service,
            model_parameter_cache=self.model_parameter_cache,
            model_parameter_manager=self.model_parameter_manager,
            model_parameter_mutations=self.model_parameter_mutations,
            model_registry=self.model_registry,
            model_resolution_service=self.model_resolution_service,
            model_services_ready_event=self.model_services_ready_event,
            plugin_manager=self.plugin_manager,
            set_installed_plugin_names=self.set_installed_plugin_names,
            shutdown_event=self.shutdown_event,
            task_registry=self.task_registry,
        )
