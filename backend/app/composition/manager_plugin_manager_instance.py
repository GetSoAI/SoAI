"""SoAI - Plugin manager instance assembly for the service graph [backend/app/composition/manager_plugin_manager_instance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.composition.build_plugin_manager import build_plugin_manager
from app.composition.manager_precondition_resolution import (
    resolve_cancellation_preconditions,
    resolve_database_preconditions,
    resolve_infrastructure_preconditions,
)
from app.composition.manager_preconditions import ManagerPreconditions
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.types_services_foundation import InfrastructureServices
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.licensing.types import Edition
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol

if TYPE_CHECKING:
    from app.composition.manager_bootstrap_types import ModelBootstrapComponents

__all__ = ("build_plugin_manager_instance",)


async def build_plugin_manager_instance(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    routing_config: RoutingConfig,
    runtime_flags: RuntimeFlagsViewProtocol,
    plugin_directory: str,
    backends_directory: str,
    updater_module_dependencies: ApplicationUpdaterModuleDependencies,
    edition: Edition,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    infrastructure_services: InfrastructureServices,
    preconditions: ManagerPreconditions,
    config_manager: ConfigManagerProtocol,
    model_bootstrap_components: ModelBootstrapComponents,
) -> PluginManagerProtocol:
    (
        event_bus,
        log_manager,
        task_registry,
        task_registry_queries,
        http_client,
        hardware_manager,
        command_executor,
        metrics_manager,
        state_aggregator,
        authoritative_plugin_state_transitions,
    ) = resolve_infrastructure_preconditions(preconditions)
    (
        _database_models,
        database_plugins,
        database_hardware,
        _database_users,
        _database_tokens,
        _database_api_keys,
        _database_mcp_access_tokens,
        _database_prompts,
        _database_conversations,
        _database_chat_identity_defaults,
        _database_chat_model_defaults,
        _database_messages,
        _database_messaging_accounts,
        _database_messaging_ingress,
        _database_messaging_deliveries,
        _database_notifications,
        _database_tool_calls,
    ) = resolve_database_preconditions(preconditions)
    cancellation_preconditions = resolve_cancellation_preconditions(preconditions)
    cancellation_coordinator = cancellation_preconditions[0]
    cancellation_history = cancellation_preconditions[1]
    cancellation_event_bus = cancellation_preconditions[2]
    token_collection = cancellation_preconditions[3]
    cancellation_binder = cancellation_preconditions[4]
    finalizer_tracker = cancellation_preconditions[5]
    (
        parameter_manager,
        model_database_purge_service,
        model_registry,
        model_provider_coordinator,
        _model_record_locks,
    ) = model_bootstrap_components
    return await build_plugin_manager(
        config=config,
        files=files,
        routing_config=routing_config,
        http_client=http_client,
        log_manager=log_manager,
        runtime_flags=runtime_flags,
        hardware_manager=hardware_manager,
        storage_manager=infrastructure_services.hardware.storage,
        event_bus=event_bus,
        metrics_manager=metrics_manager,
        config_manager=config_manager,
        state_aggregator=state_aggregator,
        authoritative_plugin_state_transitions=authoritative_plugin_state_transitions,
        cancellation_coordinator=cancellation_coordinator,
        cancellation_history=cancellation_history,
        cancellation_event_bus=cancellation_event_bus,
        token_collection=token_collection,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        task_registry=task_registry,
        task_registry_queries=task_registry_queries,
        database_plugins=database_plugins,
        database_hardware=database_hardware,
        parameter_manager=parameter_manager,
        model_registry=model_registry,
        model_database_purge_service=model_database_purge_service,
        model_provider_coordinator=model_provider_coordinator,
        plugin_directory=plugin_directory,
        backends_directory=backends_directory,
        updater_module_dependencies=updater_module_dependencies,
        edition=edition,
        lifecycle_coordinator=lifecycle_coordinator,
        command_executor=command_executor,
    )
