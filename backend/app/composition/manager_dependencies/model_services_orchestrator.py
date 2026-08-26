"""SoAI - Model services and orchestrator dependency assembly [backend/app/composition/manager_dependencies/model_services_orchestrator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.composition.build_models import build_model_services
from app.composition.manager_precondition_resolution import (
    resolve_cancellation_preconditions,
    resolve_database_preconditions,
    resolve_infrastructure_preconditions,
)
from app.composition.manager_preconditions import ManagerPreconditions
from app.composition.model_service_resolution import (
    require_model_orchestration_services,
)
from app.composition.model_services_core_dependencies import (
    ModelServicesCoreDependencies,
)
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.types_services_runtime import ModelServices
from core.config.protocols import ConfigProtocol
from core.events.protocols import DurableEventDeliveryProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.logging.trace import get_logger
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ModelManagerProtocol,
    ModelResolutionServiceProtocol,
)
from core.orchestrator.routing_config import RoutingConfig, RoutingConfigHolder
from core.plugins.protocols import PluginManagerProtocol
from orchestrator.lifecycle.start_task_tracking import SchedulerStartTaskTracker
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from app.composition.manager_bootstrap_types import ModelBootstrapComponents
    from core.openai.token_counter import PromptTokenCounter

__all__ = ("build_model_services_and_orchestrator_dependencies",)

LOGGER_NAME = "SoAI.app.composition.model_services_orchestrator"


def build_model_services_and_orchestrator_dependencies(
    *,
    config: ConfigProtocol,
    routing_config: RoutingConfig,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    preconditions: ManagerPreconditions,
    plugin_manager: PluginManagerProtocol,
    model_bootstrap_components: ModelBootstrapComponents,
    prompt_token_counter: PromptTokenCounter,
    domain_event_delivery: DurableEventDeliveryProtocol,
    licensing_status: LicensingStatusProtocol,
) -> tuple[
    ModelServices,
    OrchestratorDependencies,
    ModelManagerProtocol,
    ModelResolutionServiceProtocol,
    ModelInformationServiceProtocol,
    PluginManagerProtocol,
]:
    routing_config_holder = RoutingConfigHolder(routing_config=routing_config)
    (
        event_bus,
        _log_manager_instance,
        task_registry,
        _task_registry_queries_instance,
        _http_client_instance,
        _hardware_manager_instance,
        _command_executor_instance,
        metrics_manager,
        state_aggregator,
        authoritative_plugin_state_transitions,
    ) = resolve_infrastructure_preconditions(preconditions)
    (
        database_models,
        database_plugins,
        _database_hardware_instance,
        _database_users_instance,
        _database_tokens_instance,
        database_api_keys,
        _database_mcp_access_tokens_instance,
        _database_prompts_instance,
        _database_conversations_instance,
        _database_chat_identity_defaults_instance,
        _database_chat_model_defaults_instance,
        _database_messages_instance,
        _database_messaging_accounts_instance,
        _database_messaging_ingress_instance,
        _database_messaging_deliveries_instance,
        _database_notifications_instance,
        _database_tool_calls_instance,
    ) = resolve_database_preconditions(preconditions)
    (
        cancellation_coordinator,
        cancellation_history,
        cancellation_event_bus,
        token_collection,
        cancellation_binder,
        finalizer_tracker,
    ) = resolve_cancellation_preconditions(preconditions)
    (
        parameter_manager,
        _model_database_purge_service,
        model_registry,
        model_provider_coordinator,
        model_record_locks,
    ) = model_bootstrap_components
    core_deps = ModelServicesCoreDependencies(
        config=config,
        routing_config=routing_config,
        routing_config_holder=routing_config_holder,
        event_bus=event_bus,
        domain_event_delivery=domain_event_delivery,
        metrics_manager=metrics_manager,
        state_aggregator=state_aggregator,
        cancellation_history=cancellation_history,
        cancellation_event_bus=cancellation_event_bus,
        token_collection=token_collection,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        task_registry=task_registry,
        database_models=database_models,
        database_plugins=database_plugins,
        plugin_manager=plugin_manager,
        parameter_manager=parameter_manager,
        model_registry=model_registry,
        model_database_purge_service=_model_database_purge_service,
        model_record_locks=model_record_locks,
        lifecycle_coordinator=lifecycle_coordinator,
    )
    model_services = build_model_services(
        core_deps=core_deps,
        model_provider_coordinator=model_provider_coordinator,
    )
    (
        model_manager_instance,
        model_resolution_service,
        model_information_service,
        model_parameter_service,
        model_virtual_model_service,
    ) = require_model_orchestration_services(model_services)
    orchestrator_dependencies = OrchestratorDependencies(
        config=config,
        bus=event_bus,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_parameter_service=model_parameter_service,
        model_virtual_model_service=model_virtual_model_service,
        param_manager=parameter_manager,
        database_models=database_models,
        database_plugins=database_plugins,
        database_api_keys=database_api_keys,
        model_services_ready_event=model_manager_instance.model_services_ready_event,
        plugin_manager=plugin_manager,
        routing_config=routing_config,
        routing_config_holder=routing_config_holder,
        metrics=metrics_manager,
        state_aggregator=state_aggregator,
        authoritative_plugin_state_transitions=authoritative_plugin_state_transitions,
        audit_logger=get_logger(LOGGER_NAME),
        cancellation_coordinator=cancellation_coordinator,
        cancellation_history=cancellation_history,
        scheduler_start_task_tracker=SchedulerStartTaskTracker(),
        task_cancellation_binder=cancellation_binder,
        task_finalizer_tracker=finalizer_tracker,
        prompt_token_counter=prompt_token_counter,
        licensing_status=licensing_status,
    )
    return (
        model_services,
        orchestrator_dependencies,
        model_manager_instance,
        model_resolution_service,
        model_information_service,
        plugin_manager,
    )
