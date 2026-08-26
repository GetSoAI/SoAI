"""SoAI - MCP subsystem composition builder [backend/app/composition/build_mcp.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import contextvars
from typing import TYPE_CHECKING

import httpx2

from app.composition.build_mcp_server_components import build_mcp_server_components
from app.composition.build_mcp_server_runtime import build_mcp_server_runtime_bundle
from app.internal_protocols import LifecycleCoordinatorProtocol
from app.media_parsing_services import MediaParsingServices
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
from core.events.protocols import EventBusProtocol
from core.external_accounts.linked_account_types import LinkedAccountCapabilities
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.files.protocols import DatabaseFilesProtocol
from core.hardware.protocols import (
    HardwareControlServiceProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.licensing.protocols import LicensingStatusProtocol
from core.mail.protocols import MailServiceProtocol
from core.mcp.protocols_storage import DatabaseMCPProtocol, DatabaseMemoryProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ModelResolutionServiceProtocol,
    VirtualModelServiceProtocol,
)
from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.plugins.protocols import PluginManagerProtocol
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
from files.parsers.messaging.detection import detect_messaging_platform
from files.parsers.registry import create_messaging_parser_registry
from mcp.coordinator import MCPServicesCoordinator, MCPServicesCoordinatorDependencies
from mcp.registry.connection import (
    MCPConnectionRegistry,
    MCPConnectionRegistryDependencies,
)
from mcp.remote.connection_manager import MCPConnectionManager
from mcp.remote.dependencies import MCPRemoteDependencies
from mcp.remote.service import MCPRemote
from mcp.server.dependencies import MCPServerDependencies
from mcp.server.service import MCPServer

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.timing.startup_timings import StartupTimingsRecorder

__all__ = ("build_mcp_services_coordinator",)


def build_mcp_services_coordinator(
    *,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    http_client: httpx2.AsyncClient,
    storage_manager: StorageManagerProtocol,
    hardware_manager: HardwareManagerProtocol,
    hardware_control: HardwareControlServiceProtocol,
    hardware_soaibench: SoAIBenchServiceProtocol,
    terminal: TerminalServiceProtocol,
    database_files: DatabaseFilesProtocol,
    database_conversation_knowledge_attachments: DatabaseConversationKnowledgeAttachmentsProtocol,
    database_knowledge_prompt_state: DatabaseKnowledgePromptStateProtocol,
    database_memory: DatabaseMemoryProtocol | None,
    database_users: DatabaseUsersProtocol,
    database_conversations: DatabaseConversationsProtocol,
    database_messages: DatabaseMessagesProtocol,
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol,
    database_agent_todo_state: DatabaseAgentTodoStateProtocol,
    database_agent_plan: DatabaseAgentPlanProtocol,
    database_prompts: DatabasePromptsProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    database_password_vault: DatabasePasswordVaultProtocol,
    database_automations: DatabaseAutomationsProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
    database_automation_runs: DatabaseAutomationRunsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    database_read_video: DatabaseReadVideoJobsProtocol,
    database_plugins: DatabasePluginsProtocol,
    database_tasks: DatabaseTasksProtocol,
    database_mcp: DatabaseMCPProtocol,
    event_bus: EventBusProtocol,
    task_registry: TaskRegistryProtocol,
    task_registry_queries: TaskRegistryQueryView,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_virtual_model_service: VirtualModelServiceProtocol,
    plugin_manager: PluginManagerProtocol,
    metrics_manager: MetricsManagerProtocol,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
    secret_handle_store: SecretHandleStore,
    external_accounts: ExternalAccountsServiceProtocol,
    mail_accounts: LinkedAccountCapabilities,
    calendar_accounts: LinkedAccountCapabilities,
    mail: MailServiceProtocol,
    calendar: CalendarServiceProtocol,
    prompt_token_counter: PromptTokenCounter,
    startup_timings: StartupTimingsRecorder,
    media_parsing: MediaParsingServices,
    licensing_status: LicensingStatusProtocol,
) -> MCPServicesCoordinator:
    active_client_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
        "mcp_active_client_context",
        default=None,
    )
    active_task_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
        "mcp_active_task_context",
        default=None,
    )
    active_user_id_context: contextvars.ContextVar[int] = contextvars.ContextVar(
        "mcp_active_user_id_context",
        default=0,
    )
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None] = (
        contextvars.ContextVar(
            "mcp_active_tool_call_context",
            default=None,
        )
    )
    active_request_context: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
        "mcp_active_request_context",
        default=None,
    )
    mcp_connection_registry = MCPConnectionRegistry(
        MCPConnectionRegistryDependencies(
            connections={},
            connections_lock=asyncio.Lock(),
        ),
    )
    mcp_remote_instance = MCPRemote(
        MCPRemoteDependencies(
            config=config,
            database_mcp=database_mcp,
            database_plugins=database_plugins,
            runtime_flags=runtime_flags,
            event_bus=event_bus,
            http_client=http_client,
            connection_registry=mcp_connection_registry,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            metrics_manager=metrics_manager,
            connection_manager_builder=MCPConnectionManager,
        ),
    )

    mcp_server_dependencies = MCPServerDependencies(
        config=config,
        licensing_status=licensing_status,
        storage_manager=storage_manager,
        hardware_manager=hardware_manager,
        hardware_control=hardware_control,
        hardware_soaibench=hardware_soaibench,
        runtime_flags=runtime_flags,
        active_client_context=active_client_context,
        active_task_context=active_task_context,
        active_user_id_context=active_user_id_context,
        active_tool_call_context=active_tool_call_context,
        active_request_context=active_request_context,
        database_files=database_files,
        database_conversation_knowledge_attachments=database_conversation_knowledge_attachments,
        database_knowledge_prompt_state=database_knowledge_prompt_state,
        database_users=database_users,
        database_conversations=database_conversations,
        database_messages=database_messages,
        database_agent_event_sequences=database_agent_event_sequences,
        database_agent_todo_state=database_agent_todo_state,
        database_agent_plan=database_agent_plan,
        database_prompts=database_prompts,
        database_notifications=database_notifications,
        conversation_attention=conversation_attention,
        database_password_vault=database_password_vault,
        database_automations=database_automations,
        database_chat_identity_defaults=database_chat_identity_defaults,
        database_chat_model_defaults=database_chat_model_defaults,
        database_automation_runs=database_automation_runs,
        database_tool_calls=database_tool_calls,
        database_read_video=database_read_video,
        database_plugins=database_plugins,
        database_tasks=database_tasks,
        event_bus=event_bus,
        task_registry=task_registry,
        task_registry_queries=task_registry_queries,
        cancellation_history=cancellation_history,
        cancellation_event_bus=cancellation_event_bus,
        token_collection=token_collection,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        model_resolution_service=model_resolution_service,
        model_information_service=model_information_service,
        model_virtual_model_service=model_virtual_model_service,
        plugin_manager=plugin_manager,
        metrics_manager=metrics_manager,
        connection_registry=mcp_connection_registry,
        mcp_remote=mcp_remote_instance,
        prompt_token_counter=prompt_token_counter,
        external_accounts=external_accounts,
        mail_account_queries=mail_accounts.queries,
        calendar_account_queries=calendar_accounts.queries,
        mail=mail,
        calendar=calendar,
        terminal=terminal,
        database_memory=database_memory,
        http_client=http_client,
        secret_handle_store=secret_handle_store,
        parser_registry_factory=media_parsing.parser_registry_factory,
        document_reader=media_parsing.document_reader,
        read_audio_gateway=media_parsing.read_audio_service,
        messaging_platform_detector=detect_messaging_platform,
        messaging_parser_registry_factory=create_messaging_parser_registry,
        server_components_builder=build_mcp_server_components,
    )
    mcp_server_instance = MCPServer(mcp_server_dependencies)
    mcp_server_instance.attach_runtime(
        build_mcp_server_runtime_bundle(
            server=mcp_server_instance,
            dependencies=mcp_server_dependencies,
            startup_timings=startup_timings,
        ),
    )
    mcp_remote_instance.attach_server(mcp_server_instance)
    coordinator = MCPServicesCoordinator(
        MCPServicesCoordinatorDependencies(
            remote=mcp_remote_instance,
            server=mcp_server_instance,
        ),
    )
    lifecycle_coordinator.register_actor(coordinator)
    return coordinator
