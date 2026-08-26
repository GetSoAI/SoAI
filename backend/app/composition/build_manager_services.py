"""SoAI - Manager service graph composition [backend/app/composition/build_manager_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from app.application_dependencies import ApplicationUpdaterModuleDependencies
from app.background.messaging_gateway import MessagingGateway
from app.background.messaging_gateway_dependencies import MessagingGatewayDependencies
from app.composition.build_manager_runtime_services import (
    build_manager_runtime_services,
)
from app.composition.build_model_bootstrap import build_model_bootstrap_components
from app.composition.build_webui import build_webui_manager
from app.composition.manager_dependencies.model_services_orchestrator import (
    build_model_services_and_orchestrator_dependencies,
)
from app.composition.manager_orchestrator_components import (
    build_orchestrator_components_and_register,
)
from app.composition.manager_plugin_manager_instance import (
    build_plugin_manager_instance,
)
from app.composition.manager_precondition_resolution import (
    resolve_cancellation_preconditions,
    resolve_database_preconditions,
    resolve_infrastructure_preconditions,
)
from app.composition.manager_preconditions import ManagerPreconditions
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.types_services_foundation import InfrastructureServices
from app.types_services_runtime import (
    ModelContextProtocolServices,
    ModelServices,
    OrchestratorServices,
    PluginServices,
    StorageServices,
)
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.licensing.types import Edition
from core.logging.trace import get_logger
from core.orchestrator.routing_config import RoutingConfig
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol
from core.timing.monotonic import monotonic_ms
from core.webui_manager.protocols import WebUIManagerDatabaseDependencies

if TYPE_CHECKING:
    from app.composition.manager_bootstrap_types import ModelBootstrapComponents
    from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("build_manager_services",)

LOGGER_NAME = "SoAI.app.composition.build_manager_services"


async def build_manager_services(
    config: ConfigProtocol,
    files: FilesProtocol,
    routing_config: RoutingConfig,
    runtime_state: RuntimeStateStoreProtocol,
    preconditions: ManagerPreconditions,
    infrastructure_services: InfrastructureServices,
    runtime_flags: RuntimeFlagsViewProtocol,
    plugin_directory: str,
    backends_directory: str,
    config_manager: ConfigManagerProtocol,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    *,
    updater_module_dependencies: ApplicationUpdaterModuleDependencies,
    lifecycle_logger: logging.Logger,
    startup_timings: StartupTimingsRecorder,
    licensing_status: LicensingStatusProtocol,
    edition: Edition,
) -> tuple[
    InfrastructureServices,
    PluginServices,
    OrchestratorServices,
    StorageServices,
    ModelContextProtocolServices,
    ModelServices,
]:
    (
        _event_bus,
        _log_manager,
        _task_registry,
        _task_registry_queries,
        http_client,
        _hardware_manager,
        _command_executor,
        _metrics_manager,
        _state_aggregator,
        _authoritative_plugin_state_transitions,
    ) = resolve_infrastructure_preconditions(preconditions)
    (
        database_models,
        database_plugins,
        _database_hardware,
        database_users,
        database_tokens,
        database_api_keys,
        database_mcp_access_tokens,
        database_prompts,
        database_conversations,
        _database_chat_identity_defaults,
        _database_chat_model_defaults,
        database_messages,
        database_messaging_accounts,
        database_messaging_ingress,
        database_messaging_deliveries,
        database_notifications,
        database_tool_calls,
    ) = resolve_database_preconditions(preconditions)
    (
        _cancellation_coordinator,
        cancellation_history,
        cancellation_event_bus,
        token_collection,
        cancellation_binder,
        finalizer_tracker,
    ) = resolve_cancellation_preconditions(preconditions)
    step_started_ms = monotonic_ms()
    (
        parameter_manager,
        model_database_purge_service,
        model_registry,
        model_provider_coordinator,
        model_record_locks,
    ) = build_model_bootstrap_components(
        database_models=database_models,
        database_plugins=database_plugins,
        event_bus=infrastructure_services.event_bus,
    )
    startup_timings.record_since_ms("assembly.manager.model_bootstrap_ms", step_started_ms)
    model_bootstrap_components: ModelBootstrapComponents = (
        parameter_manager,
        model_database_purge_service,
        model_registry,
        model_provider_coordinator,
        model_record_locks,
    )
    step_started_ms = monotonic_ms()
    plugin_manager = await build_plugin_manager_instance(
        config=config,
        files=files,
        routing_config=routing_config,
        runtime_flags=runtime_flags,
        plugin_directory=plugin_directory,
        backends_directory=backends_directory,
        updater_module_dependencies=updater_module_dependencies,
        lifecycle_coordinator=lifecycle_coordinator,
        infrastructure_services=infrastructure_services,
        preconditions=preconditions,
        config_manager=config_manager,
        model_bootstrap_components=model_bootstrap_components,
    )
    startup_timings.record_since_ms("assembly.manager.plugin_manager_instance_ms", step_started_ms)
    step_started_ms = monotonic_ms()
    (
        model_services,
        orchestrator_dependencies,
        _model_manager_instance,
        model_resolution_service,
        model_information_service,
        plugin_manager,
    ) = build_model_services_and_orchestrator_dependencies(
        config=config,
        routing_config=routing_config,
        lifecycle_coordinator=lifecycle_coordinator,
        preconditions=preconditions,
        plugin_manager=plugin_manager,
        model_bootstrap_components=model_bootstrap_components,
        prompt_token_counter=infrastructure_services.prompt_token_counter,
        domain_event_delivery=infrastructure_services.domain_event_delivery,
        licensing_status=licensing_status,
    )
    startup_timings.record_since_ms("assembly.manager.model_services_ms", step_started_ms)
    step_started_ms = monotonic_ms()
    orchestrator_control_instance, orchestrator_components = (
        build_orchestrator_components_and_register(
            config=config,
            preconditions=preconditions,
            lifecycle_coordinator=lifecycle_coordinator,
            plugin_manager=plugin_manager,
            orchestrator_dependencies=orchestrator_dependencies,
        )
    )
    startup_timings.record_since_ms("assembly.manager.orchestrator_components_ms", step_started_ms)
    step_started_ms = monotonic_ms()
    messaging_gateway = MessagingGateway(
        MessagingGatewayDependencies(
            runtime_state=runtime_state,
            runtime_flags=runtime_flags,
            http_client=http_client,
            database_messaging_accounts=database_messaging_accounts,
            database_messaging_ingress=database_messaging_ingress,
            database_messaging_deliveries=database_messaging_deliveries,
            durable_delivery=infrastructure_services.domain_event_delivery,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            event_bus=_event_bus,
            licensing_status=licensing_status,
        ),
    )
    infrastructure_services = replace(
        infrastructure_services,
        messaging_gateway=messaging_gateway,
    )
    startup_timings.record_since_ms("assembly.manager.messaging_gateway_ms", step_started_ms)
    step_started_ms = monotonic_ms()
    get_logger(LOGGER_NAME).info("Loading SoAI components, please wait...")
    webui_manager = build_webui_manager(
        config=config,
        files=files,
        runtime_flags=runtime_flags,
        token_collection=token_collection,
        cancellation_history=cancellation_history,
        cancellation_event_bus=cancellation_event_bus,
        database_core=preconditions.database_core,
        database=WebUIManagerDatabaseDependencies(
            database_users=database_users,
            database_tokens=database_tokens,
            database_api_keys=database_api_keys,
            database_mcp_access_tokens=database_mcp_access_tokens,
            database_prompts=database_prompts,
            database_conversations=database_conversations,
            database_messages=database_messages,
            database_notifications=database_notifications,
            database_tool_calls=database_tool_calls,
            database_plugins=database_plugins,
        ),
        storage_manager=infrastructure_services.storage_manager,
    )
    startup_timings.record_since_ms("assembly.manager.webui_manager_ms", step_started_ms)
    plugin_services = PluginServices(
        plugin_manager=plugin_manager,
        webui_manager=webui_manager,
    )
    step_started_ms = monotonic_ms()
    (
        orchestrator_services,
        storage_services,
        model_context_protocol_services,
    ) = build_manager_runtime_services(
        config=config,
        files=files,
        runtime_flags=runtime_flags,
        http_client=http_client,
        runtime_state=runtime_state,
        preconditions=preconditions,
        infrastructure_services=infrastructure_services,
        config_manager=config_manager,
        lifecycle_coordinator=lifecycle_coordinator,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_virtual_model_service=model_services.model_virtual_model_service,
        plugin_manager=plugin_manager,
        orchestrator_control_instance=orchestrator_control_instance,
        lifecycle_logger=lifecycle_logger,
        orchestrator_components=orchestrator_components,
        startup_timings=startup_timings,
        licensing_status=licensing_status,
        edition=edition,
    )
    startup_timings.record_since_ms("assembly.manager.runtime_services_ms", step_started_ms)
    return (
        infrastructure_services,
        plugin_services,
        orchestrator_services,
        storage_services,
        model_context_protocol_services,
        model_services,
    )
