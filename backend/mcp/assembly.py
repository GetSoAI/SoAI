"""SoAI - MCP server component assembly [backend/mcp/assembly.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx2

from core.automation.protocols_database import (
    DatabaseAutomationRunsProtocol,
    DatabaseAutomationsProtocol,
)
from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.config.protocols import ConfigProtocol
from core.conversations.protocols_database_agents import (
    DatabaseAgentEventSequencesProtocol,
    DatabaseAgentPlanProtocol,
    DatabaseAgentTodoStateProtocol,
)
from core.conversations.protocols_database_conversation_records import (
    DatabaseConversationsProtocol,
)
from core.conversations.protocols_database_conversations import (
    DatabaseMessagesProtocol,
)
from core.conversations.protocols_database_defaults import (
    DatabaseChatIdentityDefaultsProtocol,
    DatabaseChatModelDefaultsProtocol,
)
from core.conversations.protocols_database_password_vault import (
    DatabasePasswordVaultProtocol,
)
from core.errors.exceptions import StateError
from core.events.protocols import EventBusProtocol
from core.files.path_resolver import ConfigFilesPathResolver
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
from core.logging.protocols import LoggerProtocol
from core.mcp.protocols_main import MCPRemoteProtocol
from core.mcp.protocols_storage import DatabaseMemoryProtocol
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ModelResolutionServiceProtocol,
    VirtualModelServiceProtocol,
)
from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.runtime.request_context import RequestContext
from core.secrets.handle_store import SecretHandleStore
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.terminal.protocols import TerminalServiceProtocol
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from core.users.protocols_database import DatabaseUsersProtocol
from mcp.rag.scraper.dependencies import build_web_content_fetcher_dependencies
from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol
from mcp.rag.scraper.service import WebContentFetcher
from mcp.tools.browser.session_store import BrowserSessionStore
from mcp.tools.runtime_sessions import MCPToolRuntimeSessionStore
from mcp.tools.service import MCPUtilityTools, MCPUtilityToolsDependencies
from mcp.tools.validation import validate_tool_definitions

if TYPE_CHECKING:
    from core.mcp.protocols_main import ReadAudioGatewayProtocol
    from core.openai.token_counter import PromptTokenCounter

__all__ = (
    "create_utility_tools",
    "create_web_fetcher",
)


def create_web_fetcher(
    http_client: httpx2.AsyncClient | None,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    storage_manager: StorageManagerProtocol,
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]],
    adblock_service: EasyListAdblockServiceProtocol | None = None,
) -> WebContentFetcherProtocol | None:
    if not http_client:
        return None
    return WebContentFetcher(
        build_web_content_fetcher_dependencies(
            http_client=http_client,
            config=config,
            runtime_flags=runtime_flags,
            storage_manager=storage_manager,
            parser_registry_factory=parser_registry_factory,
            adblock_service=adblock_service,
        ),
    )


def create_utility_tools(
    http_client: httpx2.AsyncClient | None,
    web_fetcher: WebContentFetcherProtocol | None,
    config: ConfigProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
    storage_manager: StorageManagerProtocol,
    hardware_manager: HardwareManagerProtocol,
    hardware_control: HardwareControlServiceProtocol,
    hardware_soaibench: SoAIBenchServiceProtocol,
    active_client_context: contextvars.ContextVar[str | None],
    active_user_id_context: contextvars.ContextVar[int],
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None],
    active_request_context: contextvars.ContextVar[RequestContext | None],
    database_files: DatabaseFilesProtocol,
    database_memory: DatabaseMemoryProtocol | None,
    database_plugins: DatabasePluginsProtocol,
    database_users: DatabaseUsersProtocol,
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol,
    database_agent_todo_state: DatabaseAgentTodoStateProtocol,
    database_agent_plan: DatabaseAgentPlanProtocol,
    database_conversations: DatabaseConversationsProtocol,
    database_messages: DatabaseMessagesProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    database_password_vault: DatabasePasswordVaultProtocol,
    database_automations: DatabaseAutomationsProtocol,
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol,
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol,
    database_automation_runs: DatabaseAutomationRunsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    database_read_video: DatabaseReadVideoJobsProtocol,
    task_registry: TaskRegistryProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    model_resolution_service: ModelResolutionServiceProtocol,
    model_information_service: ModelInformationServiceProtocol,
    model_virtual_model_service: VirtualModelServiceProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    secret_handle_store: SecretHandleStore,
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]],
    document_reader: DocumentReaderProtocol,
    messaging_platform_detector: Callable[[str], str | None],
    messaging_parser_registry_factory: Callable[[], dict[str, FileParserProtocol]],
    terminal: TerminalServiceProtocol,
    mcp_remote: MCPRemoteProtocol,
    prompt_token_counter: PromptTokenCounter,
    event_bus: EventBusProtocol,
    logger: LoggerProtocol,
    read_audio_gateway: ReadAudioGatewayProtocol,
    adblock_service: EasyListAdblockServiceProtocol | None = None,
) -> MCPUtilityTools:
    runtime_sessions = MCPToolRuntimeSessionStore(
        config=config,
        active_client_context=active_client_context,
        active_user_id_context=active_user_id_context,
    )
    browser_sessions = BrowserSessionStore(
        config=config,
        runtime_flags=runtime_flags,
        active_client_context=active_client_context,
        runtime_sessions=runtime_sessions,
        storage_manager=storage_manager,
        cancellation_binder=cancellation_binder,
        finalizer_tracker=finalizer_tracker,
        adblock_service=adblock_service,
    )
    logger.debug("MCP utility runtime session state is process-local.")
    utility_tools = MCPUtilityTools(
        MCPUtilityToolsDependencies(
            config=config,
            runtime_flags=runtime_flags,
            storage_manager=storage_manager,
            hardware_manager=hardware_manager,
            hardware_control=hardware_control,
            hardware_soaibench=hardware_soaibench,
            http_client=http_client,
            web_fetcher=web_fetcher,
            read_audio_gateway=read_audio_gateway,
            event_bus=event_bus,
            active_tool_call_context=active_tool_call_context,
            active_request_context=active_request_context,
            files=ConfigFilesPathResolver(config),
            database_files=database_files,
            database_memory=database_memory,
            database_plugins=database_plugins,
            database_users=database_users,
            database_agent_event_sequences=database_agent_event_sequences,
            database_agent_todo_state=database_agent_todo_state,
            database_agent_plan=database_agent_plan,
            database_conversations=database_conversations,
            database_messages=database_messages,
            database_read_video=database_read_video,
            database_notifications=database_notifications,
            conversation_attention=conversation_attention,
            database_chat_identity_defaults=database_chat_identity_defaults,
            database_chat_model_defaults=database_chat_model_defaults,
            database_password_vault=database_password_vault,
            database_automations=database_automations,
            database_automation_runs=database_automation_runs,
            database_tool_calls=database_tool_calls,
            task_registry=task_registry,
            task_cancellation_binder=cancellation_binder,
            model_resolution_service=model_resolution_service,
            model_information_service=model_information_service,
            model_virtual_model_service=model_virtual_model_service,
            secret_handle_store=secret_handle_store,
            messaging_platform_detector=messaging_platform_detector,
            messaging_parser_registry_factory=messaging_parser_registry_factory,
            parser_registry_factory=parser_registry_factory,
            document_reader=document_reader,
            terminal=terminal,
            mcp_remote=mcp_remote,
            runtime_sessions=runtime_sessions,
            browser_sessions=browser_sessions,
            prompt_token_counter=prompt_token_counter,
        ),
    )
    validation_errors = validate_tool_definitions(utility_tools)
    if validation_errors:
        for error in validation_errors:
            logger.warning(error)
        raise StateError(
            f"Tool schema/implementation validation failed: {'; '.join(validation_errors)}",
        )
    return utility_tools
