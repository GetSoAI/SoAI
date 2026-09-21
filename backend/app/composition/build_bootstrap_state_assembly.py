"""SoAI - Application bootstrap state assembly [backend/app/composition/build_bootstrap_state_assembly.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from ruamel.yaml import YAML

from app.background.api_key_quota_reservation_reconciler import (
    ApiKeyQuotaReservationReconciler,
    ApiKeyQuotaReservationReconcilerDependencies,
)
from app.background.authoritative_plugin_state.dispatcher import (
    AuthoritativePluginStateDispatcher,
    AuthoritativePluginStateDispatcherDependencies,
)
from app.background.authoritative_plugin_state.transitions import (
    AuthoritativePluginStateTransitions,
    AuthoritativePluginStateTransitionsDependencies,
)
from app.background.authoritative_plugin_state.waiters import (
    AuthoritativePluginStateWaiters,
)
from app.background.automation_service import (
    AutomationService,
    AutomationServiceDependencies,
)
from app.background.conversation_input_dispatcher import (
    ConversationInputDispatcher,
    ConversationInputDispatcherDependencies,
)
from app.background.conversation_pdf_export_sweeper import (
    ConversationPdfExportSweeper,
    ConversationPdfExportSweeperDependencies,
)
from app.background.database_receipt_sweeper import (
    DatabaseReceiptSweeper,
    DatabaseReceiptSweeperDependencies,
)
from app.background.domain_event_outbox_dispatcher import (
    DomainEventOutboxDispatcher,
    DomainEventOutboxDispatcherDependencies,
)
from app.background.mutation_command_supervisor import (
    MutationCommandSupervisor,
    MutationCommandSupervisorDependencies,
)
from app.background.plugin_circuit_breaker_notifications import (
    PluginCircuitBreakerNotificationService,
    PluginCircuitBreakerNotificationServiceDependencies,
)
from app.background.webui_attachment_sweeper import (
    WebuiAttachmentSweeper,
    WebuiAttachmentSweeperDependencies,
)
from app.composition.application_bootstrap_state import ApplicationBootstrapState
from app.composition.bootstrap_state_assembly_dependencies import (
    BootstrapStateAssemblyDependencies,
)
from app.composition.build_communications_services import build_communications_services
from app.composition.build_soaibench import build_soaibench_service
from app.types_services_foundation import (
    ConfigurationServices,
    InfrastructureServices,
    TaskServices,
)
from core.app.service_groups import HardwareRuntimeServices
from core.logging.trace import get_logger
from core.secrets.handle_store import SecretHandleStore
from features.chat.attention.coordinator import (
    ConversationAttentionCoordinator,
    ConversationAttentionCoordinatorDependencies,
)
from hardware.control_service import (
    HardwareControlService,
    HardwareControlServiceDependencies,
)

__all__ = ("assemble_application_bootstrap_state",)

HARDWARE_CONTROL_LOGGER_NAME = "SoAI.hardware.control_service"


def assemble_application_bootstrap_state(
    deps: BootstrapStateAssemblyDependencies,
) -> ApplicationBootstrapState:
    authoritative_plugin_state_waiters = AuthoritativePluginStateWaiters()
    authoritative_plugin_state_transitions = AuthoritativePluginStateTransitions(
        AuthoritativePluginStateTransitionsDependencies(
            database_core=deps.database_services.core,
            state_aggregator=deps.state_aggregator,
            waiters=authoritative_plugin_state_waiters,
        ),
    )
    communications_services = build_communications_services(deps)
    deps.runtime_foundation.lifecycle_coordinator.register_actor(communications_services.sync_actor)
    hardware_control = HardwareControlService(
        HardwareControlServiceDependencies(
            hardware_manager=deps.hardware_manager,
            gpu_tuning=deps.hardware_gpu_tuning,
            runtime_flags=deps.runtime_flags_service,
            logger=get_logger(HARDWARE_CONTROL_LOGGER_NAME),
        ),
    )
    soaibench = build_soaibench_service(
        hardware_manager=deps.hardware_manager,
        database_hardware=deps.database_services.hardware,
        task_registry=deps.task_registry_result.registry,
        cancellation_binder=deps.cancellation_system.binder,
        event_bus=deps.event_bus,
        activity_registry=deps.hardware_activity_registry,
        shutdown_event=deps.runtime_foundation.runtime_state.shutdown_event,
        http_client=deps.http_client,
    )
    infrastructure_services = InfrastructureServices(
        event_bus=deps.event_bus,
        domain_event_delivery=deps.domain_event_delivery,
        log_manager=deps.log_manager,
        metrics_manager=deps.metrics_manager,
        state_aggregator=deps.state_aggregator,
        authoritative_plugin_state_transitions=authoritative_plugin_state_transitions,
        authoritative_plugin_state_dispatcher=AuthoritativePluginStateDispatcher(
            AuthoritativePluginStateDispatcherDependencies(
                config=deps.config,
                database_core=deps.database_services.core,
                event_bus=deps.event_bus,
                waiters=authoritative_plugin_state_waiters,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
            ),
        ),
        api_key_quota_reservation_reconciler=ApiKeyQuotaReservationReconciler(
            ApiKeyQuotaReservationReconcilerDependencies(
                config=deps.config,
                database_api_keys=deps.database_services.api_keys,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
            ),
        ),
        webui_attachment_sweeper=WebuiAttachmentSweeper(
            WebuiAttachmentSweeperDependencies(
                config=deps.config,
                files=deps.files,
                database_core=deps.database_services.core,
                database_attachments=deps.database_services.conversation_attachments,
                database_knowledge=deps.database_services.conversation_knowledge_attachments,
                event_bus=deps.event_bus,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
            ),
        ),
        conversation_pdf_export_sweeper=ConversationPdfExportSweeper(
            ConversationPdfExportSweeperDependencies(
                config=deps.config,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
            ),
        ),
        database_receipt_sweeper=DatabaseReceiptSweeper(
            DatabaseReceiptSweeperDependencies(
                database_core=deps.database_services.core,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
            ),
        ),
        domain_event_outbox_dispatcher=DomainEventOutboxDispatcher(
            DomainEventOutboxDispatcherDependencies(
                startup_ready_event=deps.runtime_foundation.runtime_state.startup_ready_event,
                config=deps.config,
                database_core=deps.database_services.core,
                event_bus=deps.event_bus,
                domain_event_delivery=deps.domain_event_delivery,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
            ),
        ),
        mutation_command_supervisor=MutationCommandSupervisor(
            MutationCommandSupervisorDependencies(
                startup_ready_event=deps.runtime_foundation.runtime_state.startup_ready_event,
                database_tasks=deps.database_services.tasks,
                database_plugins=deps.database_services.plugins,
                event_bus=deps.event_bus,
                task_registry=deps.task_registry_result.registry,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
                plugin_directory=deps.paths.plugin_directory,
                durable_mutations=deps.edition_composition.durable_mutations,
            ),
        ),
        plugin_circuit_breaker_notifications=PluginCircuitBreakerNotificationService(
            PluginCircuitBreakerNotificationServiceDependencies(
                event_bus=deps.event_bus,
                database_plugins=deps.database_services.plugins,
                database_users=deps.database_services.users,
                database_notifications=deps.database_services.notifications,
            ),
        ),
        automation_service=AutomationService(
            AutomationServiceDependencies(
                config=deps.config,
                database_automations=deps.database_services.automations,
                database_automation_runs=deps.database_services.automation_runs,
                database_automation_run_scheduler=deps.database_services.automation_run_scheduler,
                event_bus=deps.event_bus,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
                runtime_state=deps.runtime_foundation.runtime_state,
            ),
        ),
        conversation_input_dispatcher=ConversationInputDispatcher(
            ConversationInputDispatcherDependencies(
                event_bus=deps.event_bus,
                durable_event_delivery=deps.domain_event_delivery,
                cancellation_binder=deps.cancellation_system.binder,
                finalizer_tracker=deps.cancellation_system.finalizer_tracker,
                runtime_state=deps.runtime_foundation.runtime_state,
            ),
        ),
        http_client=deps.http_client,
        hardware=HardwareRuntimeServices(
            manager=deps.hardware_manager,
            gpu_tuning=deps.hardware_gpu_tuning,
            control=hardware_control,
            soaibench=soaibench,
            terminal=deps.terminal,
            storage=deps.storage_manager,
        ),
        prompt_token_counter=deps.prompt_token_counter,
        command_executor=deps.command_executor,
        secret_handle_store=SecretHandleStore(
            max_total_entries=deps.config.get_int("TOOLS.MCP.SECRET_PROMPT.HANDLE_STORE_MAX_TOTAL"),
            max_entries_per_user=deps.config.get_int(
                "TOOLS.MCP.SECRET_PROMPT.HANDLE_STORE_MAX_PER_USER",
            ),
        ),
        communications=communications_services,
        conversation_attention=ConversationAttentionCoordinator(
            ConversationAttentionCoordinatorDependencies(monotonic_clock=time.monotonic),
        ),
    )
    configuration_services = ConfigurationServices(
        config=deps.config,
        files=deps.files,
        routing_config=deps.routing_config,
        config_manager=deps.config_manager,
        runtime_flags=deps.runtime_flags_service,
        yaml_parser=YAML(typ="safe"),
    )
    task_services = TaskServices(
        cancellation=deps.cancellation_system,
        task_type_routing_service=deps.task_type_routing_service,
        task_registry=deps.task_registry_result.registry,
        task_registry_queries=deps.task_registry_result.queries,
    )
    return ApplicationBootstrapState(
        runtime_foundation=deps.runtime_foundation,
        configuration_foundation=deps.configuration_foundation,
        task_type_routing_service=deps.task_type_routing_service,
        event_bus=deps.event_bus,
        log_manager=deps.log_manager,
        logging_instance=deps.logging_instance,
        restart_state_manager=deps.restart_state_manager,
        paths=deps.paths,
        security=deps.security,
        database_services=deps.database_services,
        config_manager=deps.config_manager,
        task_registry=deps.task_registry_result.registry,
        task_registry_queries=deps.task_registry_result.queries,
        infrastructure_services=infrastructure_services,
        configuration_services=configuration_services,
        task_services=task_services,
    )
