"""SoAI - Model service stack assembly and ModelManager wiring [backend/app/composition/model_services_stack.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from app.composition.model_services_core_dependencies import (
    ModelServicesCoreDependencies,
)
from app.composition.model_services_parameters import build_parameter_services
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.concurrency.ttl_cache import TTLCache
from core.models.protocols import (
    ModelManagerProtocol,
    ModelParameterServiceProtocol,
    ModelResolutionServiceProtocol,
    VirtualModelServiceProtocol,
)
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from models.actions.dependencies import ModelActionsServiceDependencies
from models.actions.service import ModelActionsService
from models.discovery.service import (
    ModelDiscoveryService,
    ModelDiscoveryServiceDependencies,
)
from models.information.service import ModelInformationService
from models.manager.coordinator.dependencies import ModelManagerDependencies
from models.manager.coordinator.model_manager import ModelManager
from models.mutation_effects import (
    ModelMutationEffects,
    ModelMutationEffectsDependencies,
)
from models.parameters.cache import AsyncParameterCache
from models.resolution import ModelResolutionService, ModelResolutionServiceDependencies
from models.virtual.coordinator import VirtualModelCoordinator
from models.virtual.service import VirtualModelService, VirtualModelServiceDependencies

__all__ = ("build_model_stack_and_manager",)


def build_model_stack_and_manager(
    *,
    core_deps: ModelServicesCoreDependencies,
    installed_plugin_names_ref: Callable[[], set[str]],
    set_installed_plugin_names: Callable[[set[str]], None],
    model_services_ready_event: asyncio.Event,
    model_services_shutdown_event: asyncio.Event,
    resolution_cache_lock: asyncio.Lock,
    resolution_cache: TTLCache[str, str],
    parameter_cache: AsyncParameterCache,
    model_record_locks: AsyncLockRegistryProtocol[str],
    model_information_service: ModelInformationService,
    virtual_model_coordinator: VirtualModelCoordinator,
) -> tuple[
    ModelManagerProtocol,
    ModelResolutionServiceProtocol,
    ModelParameterServiceProtocol,
    VirtualModelServiceProtocol,
]:
    config = core_deps.config
    event_bus = core_deps.event_bus
    metrics_manager = core_deps.metrics_manager
    state_aggregator = core_deps.state_aggregator
    cancellation_history = core_deps.cancellation_history
    cancellation_event_bus = core_deps.cancellation_event_bus
    token_collection = core_deps.token_collection
    cancellation_binder = core_deps.cancellation_binder
    finalizer_tracker = core_deps.finalizer_tracker
    task_registry = core_deps.task_registry
    database_models = core_deps.database_models
    database_plugins = core_deps.database_plugins
    plugin_manager = core_deps.plugin_manager
    parameter_manager = core_deps.parameter_manager
    model_registry = core_deps.model_registry
    lifecycle_coordinator = core_deps.lifecycle_coordinator
    routing_config_holder = core_deps.routing_config_holder
    mutation_effects = ModelMutationEffects(
        ModelMutationEffectsDependencies(
            database_models=database_models,
            parameter_cache=parameter_cache,
            resolution_cache_lock=resolution_cache_lock,
            resolution_cache=resolution_cache,
            model_invalidate_list_caches=model_information_service.model_invalidate_list_caches,
            event_bus=event_bus,
        ),
    )
    model_actions_service = ModelActionsService(
        ModelActionsServiceDependencies(
            config=config,
            database_models=database_models,
            database_plugins=database_plugins,
            plugin_manager=plugin_manager,
            state_aggregator=state_aggregator,
            event_bus=event_bus,
            cancellation_history=cancellation_history,
            cancellation_event_bus=cancellation_event_bus,
            token_collection=token_collection,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            task_registry=task_registry,
            mutation_effects=mutation_effects,
            model_database_purge_service=core_deps.model_database_purge_service,
            model_record_locks=model_record_locks,
            installed_plugin_names_ref=installed_plugin_names_ref,
            model_get_info=model_information_service.model_get_info,
            spawn_tracked_task=spawn_tracked_task,
        ),
    )
    model_parameter_mutation_service, model_parameter_service = build_parameter_services(
        config=config,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        task_registry=task_registry,
        database_models=database_models,
        parameter_manager=parameter_manager,
        metrics_manager=metrics_manager,
        parameter_cache=parameter_cache,
        mutation_effects=mutation_effects,
        model_record_locks=model_record_locks,
        model_actions_service=model_actions_service,
        model_information_service=model_information_service,
        shutdown_event=model_services_shutdown_event,
    )
    model_resolution_service = ModelResolutionService(
        ModelResolutionServiceDependencies(
            database_models=database_models,
            plugin_manager=plugin_manager,
            installed_plugin_names_ref=installed_plugin_names_ref,
            resolution_cache=resolution_cache,
            resolution_cache_lock=resolution_cache_lock,
        ),
    )
    model_virtual_model_service = VirtualModelService(
        VirtualModelServiceDependencies(
            database_models=database_models,
            virtual_model_coordinator=virtual_model_coordinator,
            state_aggregator=state_aggregator,
            routing_config_holder=routing_config_holder,
            installed_plugin_names_ref=installed_plugin_names_ref,
            model_resolve_to_universal_id=model_resolution_service.model_resolve_to_universal_id,
            model_get_info_batch=model_information_service.model_get_info_batch,
            model_validate_parameters=model_parameter_service.model_validate_parameters,
            mutation_effects=mutation_effects,
        ),
    )
    model_discovery_service = ModelDiscoveryService(
        ModelDiscoveryServiceDependencies(
            config=config,
            database_models=database_models,
            plugin_manager=plugin_manager,
            state_aggregator=state_aggregator,
            metrics=metrics_manager,
            mutation_effects=mutation_effects,
            model_record_locks=model_record_locks,
            shutdown_event=model_services_shutdown_event,
            installed_plugin_names_ref=installed_plugin_names_ref,
            virtual_model_get=database_models.get_virtual_model,
            virtual_model_delete=model_virtual_model_service.virtual_model_delete,
            virtual_model_update=model_virtual_model_service.virtual_model_update,
        ),
    )
    model_manager = ModelManager(
        ModelManagerDependencies(
            config=config,
            event_bus=event_bus,
            domain_event_delivery=core_deps.domain_event_delivery,
            plugin_manager=plugin_manager,
            database_models=database_models,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            task_registry=task_registry,
            shutdown_event=model_services_shutdown_event,
            model_services_ready_event=model_services_ready_event,
            model_discovery_service=model_discovery_service,
            model_actions_service=model_actions_service,
            model_information_service=model_information_service,
            model_resolution_service=model_resolution_service,
            model_parameter_mutations=model_parameter_mutation_service,
            model_parameter_cache=parameter_cache,
            model_parameter_manager=parameter_manager,
            model_registry=model_registry,
            installed_plugin_names_ref=installed_plugin_names_ref,
            set_installed_plugin_names=set_installed_plugin_names,
        ),
    )
    lifecycle_coordinator.register_actor(model_manager)
    return (
        model_manager,
        model_resolution_service,
        model_parameter_service,
        model_virtual_model_service,
    )
