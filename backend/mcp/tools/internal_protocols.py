"""SoAI - MCP tools internal protocols and dependency bundle [backend/mcp/tools/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import httpx2

from core.automation.protocols_database import (
    DatabaseAutomationRunsProtocol,
    DatabaseAutomationsProtocol,
)
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
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.files.protocols import (
    DatabaseFilesProtocol,
    DocumentReaderProtocol,
    FileParserProtocol,
    FilesPathResolverProtocol,
)
from core.hardware.protocols import (
    HardwareControlServiceProtocol,
    HardwareManagerProtocol,
)
from core.hardware.protocols_soaibench import SoAIBenchServiceProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.mcp.protocols_main import (
    MCPRemoteProtocol,
    MCPToolRuntimeSessionShellStoreProtocol,
    MCPToolRuntimeSessionStoreProtocol,
    ReadAudioGatewayProtocol,
    ShellBackgroundServiceProtocol,
)
from core.mcp.protocols_storage import DatabaseMemoryProtocol
from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.read_video.protocols_database import DatabaseReadVideoJobsProtocol
from core.runtime.request_context import RequestContext
from core.secrets.handle_store import SecretHandleStore
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from core.terminal.protocols import TerminalServiceProtocol
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from core.tool_calls.protocols import DatabaseToolCallsProtocol
from core.users.protocols_database import DatabaseUsersProtocol
from mcp.shared_persistence_dependencies import MCPSharedPersistence

if TYPE_CHECKING:
    from core.agent.protocols import AgentSubagentServiceProtocol
    from core.models.protocols import (
        ModelInformationServiceProtocol,
        ModelResolutionServiceProtocol,
        VirtualModelServiceProtocol,
    )
    from core.openai.token_counter import PromptTokenCounter
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.scraper.internal_protocols import WebContentFetcherProtocol
    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
    from mcp.tools.generate_image_horde_rate_limit import AnonymousHordeRateGate
    from mcp.tools.news_cache import NewsResponseCache
    from mcp.tools.news_provider_control import NewsProviderAccessController
    from mcp.tools.news_query import NewsRequest

__all__ = (
    "MCPToolRuntimeSessionShellStoreProtocol",
    "MCPToolRuntimeSessionStoreProtocol",
    "MCPUtilityToolsDependencies",
    "MCPUtilityToolsDependenciesProtocol",
    "MCPUtilityToolsProtocol",
    "ReadAudioGatewayProtocol",
)


class MCPUtilityToolsDependenciesProtocol(Protocol):
    config: ConfigProtocol
    storage_manager: StorageManagerProtocol
    hardware_manager: HardwareManagerProtocol
    hardware_control: HardwareControlServiceProtocol
    hardware_soaibench: SoAIBenchServiceProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient | None
    web_fetcher: WebContentFetcherProtocol | None
    read_audio_gateway: ReadAudioGatewayProtocol
    event_bus: EventBusProtocol
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None]
    active_request_context: contextvars.ContextVar[RequestContext | None]
    files: FilesPathResolverProtocol
    database_files: DatabaseFilesProtocol | None
    database_memory: DatabaseMemoryProtocol | None
    database_plugins: DatabasePluginsProtocol
    database_users: DatabaseUsersProtocol
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    database_conversations: DatabaseConversationsProtocol
    database_messages: DatabaseMessagesProtocol
    database_notifications: DatabaseNotificationsProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    database_password_vault: DatabasePasswordVaultProtocol | None
    database_automations: DatabaseAutomationsProtocol
    database_chat_identity_defaults: DatabaseChatIdentityDefaultsProtocol
    database_chat_model_defaults: DatabaseChatModelDefaultsProtocol
    database_automation_runs: DatabaseAutomationRunsProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    database_read_video: DatabaseReadVideoJobsProtocol
    task_registry: TaskRegistryProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_virtual_model_service: VirtualModelServiceProtocol
    secret_handle_store: SecretHandleStore | None
    messaging_platform_detector: Callable[[str], str | None]
    messaging_parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    document_reader: DocumentReaderProtocol
    terminal: TerminalServiceProtocol
    mcp_remote: MCPRemoteProtocol
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol
    browser_sessions: BrowserSessionStoreProtocol
    prompt_token_counter: PromptTokenCounter
    subagent_service: AgentSubagentServiceProtocol | None
    shell_background_service: ShellBackgroundServiceProtocol | None


class NewsArticleListSearchProtocol(Protocol):
    async def search(
        self,
        utility_tools: MCPUtilityToolsProtocol,
        *,
        request: NewsRequest,
        timeout_sec: float,
    ) -> JSONDict: ...


@dataclass(frozen=True, slots=True)
class MCPUtilityToolsDependencies(
    MCPSharedPersistence,
    MCPUtilityToolsDependenciesProtocol,
):
    config: ConfigProtocol
    storage_manager: StorageManagerProtocol
    hardware_manager: HardwareManagerProtocol
    hardware_control: HardwareControlServiceProtocol
    hardware_soaibench: SoAIBenchServiceProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient | None
    web_fetcher: WebContentFetcherProtocol | None
    read_audio_gateway: ReadAudioGatewayProtocol
    event_bus: EventBusProtocol
    active_tool_call_context: contextvars.ContextVar[CurrentToolCallIdentity | None]
    active_request_context: contextvars.ContextVar[RequestContext | None]
    files: FilesPathResolverProtocol
    database_files: DatabaseFilesProtocol | None
    database_memory: DatabaseMemoryProtocol | None
    database_plugins: DatabasePluginsProtocol
    database_users: DatabaseUsersProtocol
    database_agent_event_sequences: DatabaseAgentEventSequencesProtocol
    database_agent_todo_state: DatabaseAgentTodoStateProtocol
    database_agent_plan: DatabaseAgentPlanProtocol
    database_conversations: DatabaseConversationsProtocol
    database_messages: DatabaseMessagesProtocol
    database_notifications: DatabaseNotificationsProtocol
    conversation_attention: ConversationAttentionCoordinatorProtocol
    task_registry: TaskRegistryProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    model_information_service: ModelInformationServiceProtocol
    model_virtual_model_service: VirtualModelServiceProtocol
    messaging_platform_detector: Callable[[str], str | None]
    messaging_parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    parser_registry_factory: Callable[[], dict[str, FileParserProtocol]]
    document_reader: DocumentReaderProtocol
    terminal: TerminalServiceProtocol
    mcp_remote: MCPRemoteProtocol
    runtime_sessions: MCPToolRuntimeSessionStoreProtocol
    browser_sessions: BrowserSessionStoreProtocol
    prompt_token_counter: PromptTokenCounter
    subagent_service: AgentSubagentServiceProtocol | None = None
    shell_background_service: ShellBackgroundServiceProtocol | None = None
    database_password_vault: DatabasePasswordVaultProtocol | None = None
    secret_handle_store: SecretHandleStore | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPUtilityToolsDependencies",
            browser_sessions=self.browser_sessions,
            config=self.config,
            storage_manager=self.storage_manager,
            hardware_manager=self.hardware_manager,
            hardware_control=self.hardware_control,
            hardware_soaibench=self.hardware_soaibench,
            runtime_flags=self.runtime_flags,
            read_audio_gateway=self.read_audio_gateway,
            database_agent_todo_state=self.database_agent_todo_state,
            database_agent_event_sequences=self.database_agent_event_sequences,
            database_agent_plan=self.database_agent_plan,
            database_conversations=self.database_conversations,
            database_messages=self.database_messages,
            database_plugins=self.database_plugins,
            database_users=self.database_users,
            database_notifications=self.database_notifications,
            conversation_attention=self.conversation_attention,
            model_resolution_service=self.model_resolution_service,
            model_information_service=self.model_information_service,
            model_virtual_model_service=self.model_virtual_model_service,
            event_bus=self.event_bus,
            active_tool_call_context=self.active_tool_call_context,
            active_request_context=self.active_request_context,
            files=self.files,
            mcp_remote=self.mcp_remote,
            document_reader=self.document_reader,
            messaging_parser_registry_factory=self.messaging_parser_registry_factory,
            messaging_platform_detector=self.messaging_platform_detector,
            parser_registry_factory=self.parser_registry_factory,
            prompt_token_counter=self.prompt_token_counter,
            runtime_sessions=self.runtime_sessions,
            task_registry=self.task_registry,
            task_cancellation_binder=self.task_cancellation_binder,
            terminal=self.terminal,
        )
        self.validate_shared_persistence("MCPUtilityToolsDependencies")


class MCPUtilityToolsProtocol(MCPUtilityToolsDependenciesProtocol, Protocol):
    generate_image_horde_rate_gate: AnonymousHordeRateGate
    news_provider_control: NewsProviderAccessController
    news_cache: NewsResponseCache

    @property
    def news_article_list_search(self) -> NewsArticleListSearchProtocol: ...

    def get_tool_handlers(self) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]: ...
