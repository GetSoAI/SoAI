"""SoAI - Core service container dataclasses for app composition [backend/app/types_services_foundation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskTypeRoutingServiceProtocol,
    TokenCollectionProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView

if TYPE_CHECKING:
    from httpx2 import AsyncClient
    from ruamel.yaml import YAML

    from app.background.api_key_quota_reservation_reconciler import (
        ApiKeyQuotaReservationReconciler,
    )
    from app.background.authoritative_plugin_state.dispatcher import (
        AuthoritativePluginStateDispatcher,
    )
    from app.background.automation_service import AutomationService
    from app.background.communications_sync_actor import CommunicationsSyncActor
    from app.background.conversation_input_dispatcher import ConversationInputDispatcher
    from app.background.conversation_pdf_export_sweeper import ConversationPdfExportSweeper
    from app.background.database_receipt_sweeper import DatabaseReceiptSweeper
    from app.background.domain_event_outbox_dispatcher import (
        DomainEventOutboxDispatcher,
    )
    from app.background.mutation_command_supervisor import MutationCommandSupervisor
    from app.background.plugin_circuit_breaker_notifications import (
        PluginCircuitBreakerNotificationService,
    )
    from app.background.webui_attachment_sweeper import WebuiAttachmentSweeper
    from core.calendar.protocols import CalendarServiceProtocol
    from core.config.protocols import ConfigManagerProtocol
    from core.config.runtime_config import Config
    from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
    from core.external_accounts.linked_account_types import LinkedAccountCapabilities
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.hardware.protocols import (
        HardwareControlServiceProtocol,
        HardwareGpuTuningProtocol,
        HardwareManagerProtocol,
    )
    from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.logging.protocols import LoggingManagerProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.messaging.gateway.protocols import MessagingGatewayProtocol
    from core.metrics.protocols import MetricsManagerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.orchestrator.routing_config import RoutingConfig
    from core.plugins.protocols_instance import FilesProtocol
    from core.runtime.protocols import RuntimeFlagsMutationProtocol
    from core.secrets.handle_store import SecretHandleStore
    from core.state.protocols import (
        AuthoritativePluginStateTransitionsProtocol,
        StateAggregatorProtocol,
    )
    from core.system.protocols import CommandExecutorProtocol
    from core.terminal.protocols import TerminalServiceProtocol
    from tasks.registry.registry import TaskRegistry

__all__ = (
    "ConfigurationServices",
    "InfrastructureServices",
    "TaskServices",
)


@dataclass(slots=True, frozen=True)
class ConfigurationServices:
    config: Config
    files: FilesProtocol
    routing_config: RoutingConfig
    config_manager: ConfigManagerProtocol
    runtime_flags: RuntimeFlagsMutationProtocol
    yaml_parser: YAML

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ConfigurationServices",
            config=self.config,
            files=self.files,
            routing_config=self.routing_config,
            config_manager=self.config_manager,
            runtime_flags=self.runtime_flags,
            yaml_parser=self.yaml_parser,
        )


@dataclass(slots=True, frozen=True)
class InfrastructureServices:
    event_bus: EventBusProtocol
    domain_event_delivery: DurableEventDeliveryProtocol
    log_manager: LoggingManagerProtocol
    metrics_manager: MetricsManagerProtocol
    state_aggregator: StateAggregatorProtocol
    authoritative_plugin_state_transitions: AuthoritativePluginStateTransitionsProtocol
    authoritative_plugin_state_dispatcher: AuthoritativePluginStateDispatcher
    api_key_quota_reservation_reconciler: ApiKeyQuotaReservationReconciler
    webui_attachment_sweeper: WebuiAttachmentSweeper
    conversation_pdf_export_sweeper: ConversationPdfExportSweeper
    database_receipt_sweeper: DatabaseReceiptSweeper
    domain_event_outbox_dispatcher: DomainEventOutboxDispatcher
    mutation_command_supervisor: MutationCommandSupervisor
    plugin_circuit_breaker_notifications: PluginCircuitBreakerNotificationService
    automation_service: AutomationService
    conversation_input_dispatcher: ConversationInputDispatcher
    http_client: AsyncClient
    hw_manager: HardwareManagerProtocol
    hw_gpu_tuning: HardwareGpuTuningProtocol
    hardware_control: HardwareControlServiceProtocol
    hardware_soaibench: SoAIBenchServiceProtocol
    terminal: TerminalServiceProtocol
    storage_manager: StorageManagerProtocol
    prompt_token_counter: PromptTokenCounter
    command_executor: CommandExecutorProtocol | None
    secret_handle_store: SecretHandleStore
    external_accounts: ExternalAccountsServiceProtocol
    mail_accounts: LinkedAccountCapabilities
    calendar_accounts: LinkedAccountCapabilities
    mail: MailServiceProtocol
    calendar: CalendarServiceProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    communications_sync_actor: CommunicationsSyncActor
    messaging_gateway: MessagingGatewayProtocol | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="InfrastructureServices",
            event_bus=self.event_bus,
            domain_event_delivery=self.domain_event_delivery,
            log_manager=self.log_manager,
            metrics_manager=self.metrics_manager,
            state_aggregator=self.state_aggregator,
            authoritative_plugin_state_transitions=self.authoritative_plugin_state_transitions,
            authoritative_plugin_state_dispatcher=self.authoritative_plugin_state_dispatcher,
            api_key_quota_reservation_reconciler=self.api_key_quota_reservation_reconciler,
            webui_attachment_sweeper=self.webui_attachment_sweeper,
            conversation_pdf_export_sweeper=self.conversation_pdf_export_sweeper,
            database_receipt_sweeper=self.database_receipt_sweeper,
            domain_event_outbox_dispatcher=self.domain_event_outbox_dispatcher,
            mutation_command_supervisor=self.mutation_command_supervisor,
            plugin_circuit_breaker_notifications=self.plugin_circuit_breaker_notifications,
            automation_service=self.automation_service,
            conversation_input_dispatcher=self.conversation_input_dispatcher,
            http_client=self.http_client,
            hw_manager=self.hw_manager,
            hw_gpu_tuning=self.hw_gpu_tuning,
            hardware_control=self.hardware_control,
            hardware_soaibench=self.hardware_soaibench,
            terminal=self.terminal,
            storage_manager=self.storage_manager,
            prompt_token_counter=self.prompt_token_counter,
            secret_handle_store=self.secret_handle_store,
            external_accounts=self.external_accounts,
            mail_accounts=self.mail_accounts,
            calendar_accounts=self.calendar_accounts,
            mail=self.mail,
            calendar=self.calendar,
            conversation_attention=self.conversation_attention,
            communications_sync_actor=self.communications_sync_actor,
        )


@dataclass(slots=True, frozen=True)
class TaskServices:
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    task_finalizer_tracker: TaskFinalizerTrackerProtocol
    task_type_routing_service: TaskTypeRoutingServiceProtocol
    task_registry: TaskRegistry
    task_registry_queries: TaskRegistryQueryView

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskServices",
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_history=self.cancellation_history,
            cancellation_event_bus=self.cancellation_event_bus,
            token_collection=self.token_collection,
            task_cancellation_binder=self.task_cancellation_binder,
            task_finalizer_tracker=self.task_finalizer_tracker,
            task_type_routing_service=self.task_type_routing_service,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
        )
