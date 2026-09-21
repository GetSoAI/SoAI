"""SoAI - Core service container dataclasses for app composition [backend/app/types_services_foundation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.app.protocols import (
    CancellationSystemProtocol,
    CommunicationsServicesProtocol,
)
from core.app.service_groups import HardwareRuntimeServices
from core.di.validation import require_dependencies
from core.tasks.protocols import TaskTypeRoutingServiceProtocol
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
    from core.config.protocols import ConfigManagerProtocol
    from core.config.runtime_config import Config
    from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
    from core.logging.protocols import LoggingManagerProtocol
    from core.messaging.protocols_gateway import MessagingGatewayProtocol
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
    hardware: HardwareRuntimeServices
    prompt_token_counter: PromptTokenCounter
    command_executor: CommandExecutorProtocol | None
    secret_handle_store: SecretHandleStore
    communications: CommunicationsServicesProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
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
            hardware=self.hardware,
            prompt_token_counter=self.prompt_token_counter,
            secret_handle_store=self.secret_handle_store,
            communications=self.communications,
            conversation_attention=self.conversation_attention,
        )


@dataclass(slots=True, frozen=True)
class TaskServices:
    cancellation: CancellationSystemProtocol
    task_type_routing_service: TaskTypeRoutingServiceProtocol
    task_registry: TaskRegistry
    task_registry_queries: TaskRegistryQueryView

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TaskServices",
            cancellation=self.cancellation,
            task_type_routing_service=self.task_type_routing_service,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
        )
