"""SoAI - MCP server dependency bundle [backend/mcp/server/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.attachments.protocols_database import (
    DatabaseConversationKnowledgeAttachmentsProtocol,
)
from core.automation.protocols_database import (
    DatabaseAutomationRunsProtocol,
    DatabaseAutomationsProtocol,
)
from core.calendar.protocols import CalendarServiceProtocol
from core.config.protocols import ConfigProtocol
from core.conversations.protocols_database_agents import (
    DatabaseAgentEventSequencesProtocol,
    DatabaseAgentPlanProtocol,
    DatabaseAgentTodoStateProtocol,
)
from core.conversations.protocols_database_conversation_records import (
    DatabaseConversationsProtocol,
)
from core.conversations.protocols_database_conversations import DatabaseMessagesProtocol
from core.conversations.protocols_database_defaults import (
    DatabaseChatIdentityDefaultsProtocol,
    DatabaseChatModelDefaultsProtocol,
)
from core.conversations.protocols_database_password_vault import (
    DatabasePasswordVaultProtocol,
)
from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.external_accounts.protocols import (
    ExternalAccountsServiceProtocol,
    LinkedAccountQueryProtocol,
)
from core.files.protocols import (
    DatabaseFilesProtocol,
    DocumentReaderProtocol,
    FileParserProtocol,
)
from core.hardware.protocols import (
    HardwareControlServiceProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.mail.protocols import MailServiceProtocol
from core.mcp.protocols_main import MCPRemoteProtocol
from core.mcp.protocols_storage import DatabaseMemoryProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.prompts.protocols_database import DatabasePromptsProtocol
from core.rag.protocols import DatabaseKnowledgePromptStateProtocol
from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.runtime.request_context import RequestContext
from core.secrets.handle_store import SecretHandleStore
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from core.terminal.protocols import TerminalServiceProtocol
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from core.users.protocols_database import DatabaseUsersProtocol
from mcp.registry.internal_protocols import MCPConnectionRegistryProtocol
from mcp.server.component_factory import ComponentFactoryInputs, MCPServerComponents

if TYPE_CHECKING:
    from core.mcp.protocols_main import ReadAudioGatewayProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )
    from core.openai.token_counter import PromptTokenCounter
    from core.plugins.protocols import PluginManagerProtocol

__all__ = ("MCPServerDependencies",)


@dataclass(frozen=True, slots=True)
class MCPServerDependencies:
    config: ConfigProtocol
    licensing_status: LicensingStatusProtocol
    storage_manager: StorageManagerProtocol
    hardware_manager: HardwareManagerProtocol
    hardware_control: HardwareControlServiceProtocol
    hardware_soaibench: SoAIBenchServiceProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    active_client_context: contextvars.ContextVar[str | None]
    active_task_context: contextvars.ContextVar[str | None]
    active_user_id_context: contextvars.ContextVar[int]
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None]
    active_request_context: contextvars.ContextVar[RequestContext | None]
    database_files: DatabaseFilesProtocol
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol
    database_users: DatabaseUsersProtocol
    database_conversations: DatabaseConversationsProtocol
    database_messages: DatabaseMessagesProtocol
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    database_prompts: DatabasePromptsProtocol
    database_notifications: DatabaseNotificationsProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    database_password_vault: DatabasePasswordVaultProtocol
    database_automations: DatabaseAutomationsProtocol
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol
    database_automation_runs: DatabaseAutomationRunsProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_read_video: DatabaseReadVideoJobsProtocol
    database_plugins: DatabasePluginsProtocol
    database_tasks: DatabaseTasksProtocol
    event_bus: EventBusProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    cancellation_history: CancellationHistoryProtocol
    cancellation_event_bus: CancellationEventBusProtocol
    token_collection: TokenCollectionProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_virtual_model_service: VirtualModelServiceProtocol
    plugin_manager: PluginManagerProtocol
    metrics_manager: MetricsManagerProtocol
    connection_registry: MCPConnectionRegistryProtocol
    mcp_remote: MCPRemoteProtocol
    prompt_token_counter: PromptTokenCounter
    external_accounts: ExternalAccountsServiceProtocol
    mail_account_queries: LinkedAccountQueryProtocol
    calendar_account_queries: LinkedAccountQueryProtocol
    mail: MailServiceProtocol
    calendar: CalendarServiceProtocol
    terminal: TerminalServiceProtocol
    database_memory: DatabaseMemoryProtocol | None
    secret_handle_store: SecretHandleStore
    http_client: httpx2.AsyncClient | None
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    document_reader: DocumentReaderProtocol
    read_audio_gateway: ReadAudioGatewayProtocol
    messaging_platform_detector: Callable[[str], str | None]
    messaging_parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    server_components_builder: Callable[
        [ComponentFactoryInputs, Callable[[], Coroutine[None, None, None]]],
        MCPServerComponents,
    ]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPServerDependencies",
            active_client_context=self.active_client_context,
            active_task_context=self.active_task_context,
            active_user_id_context=self.active_user_id_context,
            active_tool_call_context=self.active_tool_call_context,
            active_request_context=self.active_request_context,
            cancellation_binder=self.cancellation_binder,
            cancellation_event_bus=self.cancellation_event_bus,
            cancellation_history=self.cancellation_history,
            config=self.config,
            licensing_status=self.licensing_status,
            connection_registry=self.connection_registry,
            storage_manager=self.storage_manager,
            hardware_manager=self.hardware_manager,
            hardware_control=self.hardware_control,
            hardware_soaibench=self.hardware_soaibench,
            database_agent_event_sequences=self.database_agent_event_sequences,
            database_agent_todo_state=self.database_agent_todo_state,
            database_agent_plan=self.database_agent_plan,
            database_conversations=self.database_conversations,
            database_conversation_knowledge_attachments=(
                self.database_conversation_knowledge_attachments
            ),
            database_messages=self.database_messages,
            database_files=self.database_files,
            database_knowledge_prompt_state=self.database_knowledge_prompt_state,
            database_notifications=self.database_notifications,
            conversation_attention=self.conversation_attention,
            database_password_vault=self.database_password_vault,
            database_automation_runs=self.database_automation_runs,
            database_automations=self.database_automations,
            database_chat_identity_defaults=self.database_chat_identity_defaults,
            database_chat_model_defaults=self.database_chat_model_defaults,
            database_tool_calls=self.database_tool_calls,
            database_read_video=self.database_read_video,
            database_plugins=self.database_plugins,
            database_prompts=self.database_prompts,
            database_tasks=self.database_tasks,
            database_users=self.database_users,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            mcp_remote=self.mcp_remote,
            prompt_token_counter=self.prompt_token_counter,
            read_audio_gateway=self.read_audio_gateway,
            external_accounts=self.external_accounts,
            mail_account_queries=self.mail_account_queries,
            calendar_account_queries=self.calendar_account_queries,
            mail=self.mail,
            calendar=self.calendar,
            messaging_parser_registry_factory=self.messaging_parser_registry_factory,
            messaging_platform_detector=self.messaging_platform_detector,
            metrics_manager=self.metrics_manager,
            model_information_service=self.model_information_service,
            model_resolution_service=self.model_resolution_service,
            model_virtual_model_service=self.model_virtual_model_service,
            document_reader=self.document_reader,
            parser_registry_factory=self.parser_registry_factory,
            plugin_manager=self.plugin_manager,
            runtime_flags=self.runtime_flags,
            server_components_builder=self.server_components_builder,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            terminal=self.terminal,
            token_collection=self.token_collection,
            secret_handle_store=self.secret_handle_store,
        )
