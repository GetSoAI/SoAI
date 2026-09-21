"""SoAI - Manager runtime services assembly [backend/app/composition/build_manager_runtime_services.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.composition.build_inactivity_monitor import build_inactivity_monitor
from app.composition.build_mcp import build_mcp_services_coordinator
from app.composition.build_media_parsing import build_media_parsing_services
from app.composition.build_storage import build_storage_services
from app.composition.manager_preconditions import ManagerPreconditions
from app.composition.orchestrator_service_components import (
    OrchestratorServiceComponents,
)
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.types_services_foundation import InfrastructureServices
from app.types_services_runtime import (
    ModelContextProtocolServices,
    OrchestratorServices,
    StorageServices,
)
from core.config.protocols import ConfigManagerProtocol, ConfigProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.licensing.types import Edition
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ModelResolutionServiceProtocol,
    VirtualModelServiceProtocol,
)
from core.orchestrator.protocols_lifecycle import OrchestratorControlProtocol
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_instance import FilesProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol, RuntimeStateStoreProtocol
from core.tool_calls.protocols import ToolCallExecutorProtocol
from orchestrator.tool_calls.dependencies import ToolCallProcessorDependencies
from orchestrator.tool_calls.service import ToolCallProcessor

if TYPE_CHECKING:
    import httpx2

    from core.events.protocols import EventBusProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.timing.startup_timings import StartupTimingsRecorder
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = ("build_manager_runtime_services",)


def _build_tool_call_processor(
    *,
    database_tool_calls: DatabaseToolCallsProtocol,
    tool_executor: ToolCallExecutorProtocol,
    event_bus: EventBusProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> ToolCallProcessor:
    return ToolCallProcessor(
        ToolCallProcessorDependencies(
            database_tool_calls=database_tool_calls,
            tool_executor=tool_executor,
            event_bus=event_bus,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
        ),
    )


def build_manager_runtime_services(
    *,
    config: ConfigProtocol,
    files: FilesProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    http_client: httpx2.AsyncClient,
    runtime_state: RuntimeStateStoreProtocol,
    preconditions: ManagerPreconditions,
    infrastructure_services: InfrastructureServices,
    config_manager: ConfigManagerProtocol,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_virtual_model_service: VirtualModelServiceProtocol,
    plugin_manager: PluginManagerProtocol,
    orchestrator_control_instance: OrchestratorControlProtocol,
    lifecycle_logger: logging.Logger,
    startup_timings: StartupTimingsRecorder,
    orchestrator_components: OrchestratorServiceComponents,
    licensing_status: LicensingStatusProtocol,
    edition: Edition,
) -> tuple[
    OrchestratorServices,
    StorageServices,
    ModelContextProtocolServices,
]:
    media_parsing = build_media_parsing_services(
        config=config,
        runtime_flags=runtime_flags,
        storage_manager=infrastructure_services.hardware.storage,
    )
    mcp_coordinator_instance = build_mcp_services_coordinator(
        config=config,
        runtime_flags=runtime_flags,
        http_client=http_client,
        storage_manager=infrastructure_services.hardware.storage,
        hardware_manager=infrastructure_services.hardware.manager,
        hardware_control=infrastructure_services.hardware.control,
        hardware_soaibench=infrastructure_services.hardware.soaibench,
        terminal=infrastructure_services.hardware.terminal,
        database_files=preconditions.database_files,
        database_conversation_knowledge_attachments=(
            preconditions.database_conversation_knowledge_attachments
        ),
        database_knowledge_prompt_state=preconditions.database_knowledge_prompt_state,
        database_memory=preconditions.database_memory,
        database_users=preconditions.database_users,
        database_conversations=preconditions.database_conversations,
        database_messages=preconditions.database_messages,
        database_agent_event_sequences=preconditions.database_agent_event_sequences,
        database_agent_todo_state=preconditions.database_agent_todo_state,
        database_agent_plan=preconditions.database_agent_plan,
        database_prompts=preconditions.database_prompts,
        database_notifications=preconditions.database_notifications,
        conversation_attention=infrastructure_services.conversation_attention,
        database_password_vault=preconditions.database_password_vault,
        database_automations=preconditions.database_automations,
        database_chat_identity_defaults=preconditions.database_chat_identity_defaults,
        database_chat_model_defaults=preconditions.database_chat_model_defaults,
        database_automation_runs=preconditions.database_automation_runs,
        database_tool_calls=preconditions.database_tool_calls,
        database_read_video=preconditions.database_read_video,
        database_plugins=preconditions.database_plugins,
        database_tasks=preconditions.database_tasks,
        database_mcp=preconditions.database_mcp,
        event_bus=preconditions.event_bus,
        task_registry=preconditions.task_registry,
        task_registry_queries=preconditions.task_registry_queries,
        cancellation_history=preconditions.cancellation_history,
        cancellation_event_bus=preconditions.cancellation_event_bus,
        token_collection=preconditions.token_collection,
        cancellation_binder=preconditions.cancellation_binder,
        finalizer_tracker=preconditions.finalizer_tracker,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_virtual_model_service=model_virtual_model_service,
        plugin_manager=plugin_manager,
        metrics_manager=preconditions.metrics_manager,
        lifecycle_coordinator=lifecycle_coordinator,
        secret_handle_store=infrastructure_services.secret_handle_store,
        external_accounts=infrastructure_services.communications.external_accounts,
        mail_accounts=infrastructure_services.communications.mail_accounts,
        calendar_accounts=infrastructure_services.communications.calendar_accounts,
        mail=infrastructure_services.communications.mail,
        calendar=infrastructure_services.communications.calendar,
        prompt_token_counter=infrastructure_services.prompt_token_counter,
        startup_timings=startup_timings,
        media_parsing=media_parsing,
        licensing_status=licensing_status,
    )
    tool_executor: ToolCallExecutorProtocol = mcp_coordinator_instance.server
    tool_call_processor_instance = _build_tool_call_processor(
        database_tool_calls=preconditions.database_tool_calls,
        tool_executor=tool_executor,
        event_bus=preconditions.event_bus,
        cancellation_binder=preconditions.cancellation_binder,
        finalizer_tracker=preconditions.finalizer_tracker,
    )
    storage_services = build_storage_services(
        edition=edition,
        config=config,
        files=files,
        runtime_state=runtime_state,
        event_bus=preconditions.event_bus,
        domain_event_delivery=infrastructure_services.domain_event_delivery,
        cancellation_coordinator=preconditions.cancellation_coordinator,
        cancellation_history=preconditions.cancellation_history,
        cancellation_event_bus=preconditions.cancellation_event_bus,
        token_collection=preconditions.token_collection,
        cancellation_binder=preconditions.cancellation_binder,
        finalizer_tracker=preconditions.finalizer_tracker,
        task_registry=preconditions.task_registry,
        database_core=preconditions.database_core,
        database_notifications=preconditions.database_notifications,
        database_files=preconditions.database_files,
        orchestrator_control=orchestrator_control_instance,
        config_manager=config_manager,
        storage_manager=infrastructure_services.hardware.storage,
        lifecycle_coordinator=lifecycle_coordinator,
        media_parsing=media_parsing,
    )
    inactivity_monitor_instance = build_inactivity_monitor(
        config=config,
        event_bus=preconditions.event_bus,
        runtime_state=runtime_state,
        cancellation_binder=preconditions.cancellation_binder,
        finalizer_tracker=preconditions.finalizer_tracker,
        metrics_manager=preconditions.metrics_manager,
        lifecycle_logger=lifecycle_logger,
        lifecycle_coordinator=lifecycle_coordinator,
    )
    orchestrator_services = OrchestratorServices(
        queue=orchestrator_components.queue,
        scheduler=orchestrator_components.scheduler,
        inference_executor=orchestrator_components.inference_executor,
        outcomes=orchestrator_components.outcomes,
        active_inferences=orchestrator_components.active_inferences,
        handlers=orchestrator_components.handlers,
        lifecycle=orchestrator_components.lifecycle,
        control=orchestrator_components.control,
        tool_call_processor=tool_call_processor_instance,
        inactivity_monitor=inactivity_monitor_instance,
    )
    model_context_protocol_services = ModelContextProtocolServices(
        coordinator=mcp_coordinator_instance,
    )
    return (
        orchestrator_services,
        storage_services,
        model_context_protocol_services,
    )
