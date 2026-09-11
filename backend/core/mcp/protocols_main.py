"""SoAI - MCP protocol contracts for cross-subsystem communication [backend/core/mcp/protocols_main.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

from core.agent.protocols import AgentSubagentServiceProtocol
from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.events.protocols import EventBusProtocol
from core.mcp.protocols_runtime import (
    MCPContextProtocol,
    MCPPaginationProtocol,
    MCPRemoteHostProtocol,
    MCPSessionProtocol,
    MCPStreamingProtocol,
    MCPTaskProtocol,
)
from core.mcp.protocols_storage import MCPServerConfigProtocol
from core.mcp.requests import AddMCPServerRequest
from core.mcp.runtime_types import ShellSession, ToolWorkspaceState
from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from core.models.protocols import ModelInformationServiceProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from core.terminal.protocols import TerminalServiceProtocol
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from core.tool_calls.protocols import ToolCallExecutorProtocol

if TYPE_CHECKING:
    from core.calendar.protocols import CalendarServiceProtocol
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import (
        ExternalAccountsServiceProtocol,
        LinkedAccountQueryProtocol,
    )
    from core.licensing.protocols import LicensingStatusProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.mcp.protocols_rag import FetchedContentProtocol, MCPRAGProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ShellBackgroundServiceProtocol",
    "MCPRegistrationProtocol",
    "MCPRemoteProtocol",
    "MCPSearchApiKeysProtocol",
    "MCPSearchProtocol",
    "MCPServerProtocol",
    "MCPServicesCoordinatorProtocol",
    "MCPToolRuntimeSessionShellStoreProtocol",
    "MCPToolRuntimeSessionStoreProtocol",
    "MCPToolRuntimeSessionWorkspaceStoreProtocol",
    "MCPUtilityToolsSurfaceProtocol",
    "MCPWebFetcherProtocol",
    "ReadAudioGatewayProtocol",
    "ShellTranscriptProtocol",
)


class ReadAudioGatewayProtocol(Protocol):
    async def read_audio(
        self,
        *,
        file_path: str,
        model_name: str,
        language: str | None,
        task: str,
        include_word_timestamps: bool,
    ) -> JSONDict: ...


class ShellTranscriptProtocol(Protocol):
    def append(self, data: bytes) -> None: ...

    def read_incremental(self, *, limit: int) -> JSONDict: ...

    def read_lines(self, *, offset: int, limit: int, from_end: bool) -> JSONDict: ...

    def search(self, *, query: str, offset: int, limit: int, case_sensitive: bool) -> JSONDict: ...

    def snapshot_page(self, *, limit: int) -> JSONDict: ...

    def remove(self) -> None: ...


class MCPToolRuntimeSessionStoreProtocol(Protocol):
    def current_owner_key(self) -> str: ...

    def current_user_id(self) -> int: ...

    def require_workspace_path(self, owner_key: str | None = None) -> str: ...

    def get_or_create_workspace_state(self, owner_key: str | None = None) -> ToolWorkspaceState: ...

    def set_workspace_path(
        self,
        workspace_path: str,
        owner_key: str | None = None,
    ) -> ToolWorkspaceState: ...

    def create_shell_session(
        self,
        terminal_session_id: str,
        owner_key: str | None = None,
    ) -> ShellSession: ...

    def get_shell_session(self, session_id: int) -> ShellSession | None: ...

    def close_shell_session(self, session_id: int) -> ShellSession | None: ...

    def list_shell_sessions_for_owner(self, owner_key: str | None = None) -> list[ShellSession]: ...

    def list_shell_sessions_for_user(self, user_id: int) -> list[ShellSession]: ...

    def append_shell_output(self, session_id: int, data: bytes) -> None: ...

    def append_shell_transcript_output(self, session_id: int, data: bytes) -> None: ...

    def create_shell_transcript(self, session_id: int, transcript_root: str) -> None: ...

    def remove_shell_transcript(self, session_id: int) -> None: ...

    def read_shell_transcript_incremental(self, session_id: int, limit: int) -> JSONDict: ...

    def snapshot_shell_transcript_page(self, session_id: int, limit: int) -> JSONDict: ...

    def read_shell_transcript_lines(
        self,
        session_id: int,
        offset: int,
        limit: int,
        from_end: bool,
    ) -> JSONDict: ...

    def search_shell_transcript(
        self,
        session_id: int,
        query: str,
        offset: int,
        limit: int,
        case_sensitive: bool,
    ) -> JSONDict: ...

    def mark_shell_exit(self, session_id: int, exit_code: int) -> None: ...

    def peek_shell_session_exit(self, session_id: int) -> tuple[bool, int | None]: ...

    def drain_shell_output(self, session_id: int, max_chars: int) -> str: ...

    def snapshot_shell_output(self, session_id: int, max_chars: int) -> str: ...

    def pop_shell_sessions_pending_terminal_close(self) -> list[ShellSession]: ...

    def close_shell_session_and_queue_terminal_close(
        self,
        session_id: int,
    ) -> ShellSession | None: ...

    def requeue_shell_session_for_terminal_close(self, session: ShellSession) -> None: ...


class MCPToolRuntimeSessionShellStoreProtocol(Protocol):
    SHELL_SESSION_EXIT_TTL_SEC: float
    SHELL_SESSION_ACTIVE_IDLE_TTL_SEC: float
    SHELL_SESSION_MAX_PER_OWNER: int
    SHELL_SESSION_MAX_OUTPUT_BYTES: int
    shell_sessions: dict[int, ShellSession]
    shell_transcripts: dict[int, ShellTranscriptProtocol]
    pending_terminal_close_sessions: dict[str, ShellSession]
    next_session_id: int

    def current_owner_key(self) -> str: ...

    def current_user_id(self) -> int: ...

    def prune_shell_sessions(self) -> None: ...

    def append_shell_transcript_output(self, session_id: int, data: bytes) -> None: ...

    def remove_shell_transcript(self, session_id: int) -> None: ...


class MCPToolRuntimeSessionWorkspaceStoreProtocol(Protocol):
    WORKSPACE_IDLE_TTL_SEC: float
    WORKSPACE_MAX_PER_PROCESS: int
    workspace_states: dict[str, ToolWorkspaceState]

    def current_owner_key(self) -> str: ...

    def prune_workspace_states(self) -> None: ...

    def get_or_create_workspace_state(self, owner_key: str | None = None) -> ToolWorkspaceState: ...


class ShellBackgroundServiceProtocol(Protocol):
    async def start_background_shell_watch(
        self,
        *,
        runtime_sessions: MCPToolRuntimeSessionStoreProtocol,
        terminal: TerminalServiceProtocol,
        identity: CurrentToolCallIdentity,
        shell_session_id: int,
        terminal_session_id: str,
        tty: bool,
        max_output_chars: int,
        output_limit: int,
        trace_id: str,
        accepted_result: JSONValue,
    ) -> JSONDict: ...

    async def shutdown(self) -> None: ...


@runtime_checkable
class MCPRegistrationProtocol(Protocol):
    def registered_tool_names(self) -> list[str]: ...
    def available_local_tool_names(
        self,
        local_scope: MCPToolCatalogScope = "public",
    ) -> list[str]: ...
    def plugin_tool_definitions(self) -> dict[str, JSONDict]: ...
    def tool_definitions(
        self,
        local_scope: MCPToolCatalogScope = "public",
    ) -> dict[str, JSONDict]: ...
    def get_argument(self, parameters: JSONDict, key: str) -> JSONValue: ...
    def require_rag(self) -> MCPRAGProtocol: ...


class MCPSearchProtocol(Protocol):
    default_provider: str
    runtime_flags: RuntimeFlagsViewProtocol

    @property
    def web_fetcher(self) -> MCPWebFetcherProtocol: ...

    def list_supported_providers(self) -> list[str]: ...

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        provider: str | None = None,
        user_id: int = 0,
        owner_id: str | None = None,
        owner_type: str = "conversation",
        **search_options: JSONValue,
    ) -> list[JSONDict]: ...
    async def fetch_url(
        self,
        url: str,
        *,
        user_id: int = 0,
        owner_id: str | None = None,
        task_id: str | None = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> FetchedContentProtocol: ...


class MCPSearchApiKeysProtocol(Protocol):
    async def load_search_api_keys_from_persistence(self) -> None: ...
    async def list_search_provider_api_keys(self) -> list[JSONDict]: ...
    async def set_search_provider_api_key(self, provider: str, api_key: str) -> JSONDict: ...
    async def delete_search_provider_api_key(self, provider: str) -> bool: ...


class MCPUtilityToolsSurfaceProtocol(Protocol):
    @property
    def active_tool_call_context(
        self,
    ) -> contextvars.ContextVar[CurrentToolCallIdentity | None]: ...

    @property
    def active_request_context(
        self,
    ) -> contextvars.ContextVar[RequestContext | None]: ...

    def attach_subagent_service(self, service: AgentSubagentServiceProtocol) -> None: ...
    def attach_shell_background_service(self, service: ShellBackgroundServiceProtocol) -> None: ...


class MCPServerProtocol(ToolCallExecutorProtocol, Protocol):
    event_bus: EventBusProtocol
    config: ConfigProtocol
    external_accounts: ExternalAccountsServiceProtocol
    mail_account_queries: LinkedAccountQueryProtocol
    calendar_account_queries: LinkedAccountQueryProtocol
    mail: MailServiceProtocol
    calendar: CalendarServiceProtocol
    licensing_status: LicensingStatusProtocol

    @property
    def host_sampling_default_model(self) -> str | None: ...
    @property
    def allowed_origins(self) -> list[str]: ...
    @property
    def enabled(self) -> bool: ...
    @property
    def host_mode_enabled(self) -> bool: ...
    @property
    def server_mode_enabled(self) -> bool: ...
    @property
    def server_mode_active(self) -> bool: ...
    @property
    def registered_tools_count(self) -> int: ...
    @property
    def registered_resources_count(self) -> int: ...
    @property
    def registered_prompts_count(self) -> int: ...
    @property
    def registration(self) -> MCPRegistrationProtocol: ...
    @property
    def session(self) -> MCPSessionProtocol: ...
    @property
    def streaming(self) -> MCPStreamingProtocol: ...
    @property
    def context(self) -> MCPContextProtocol: ...
    @property
    def task(self) -> MCPTaskProtocol: ...
    @property
    def search(self) -> MCPSearchProtocol: ...
    @property
    def search_api_keys(self) -> MCPSearchApiKeysProtocol: ...
    @property
    def pagination(self) -> MCPPaginationProtocol: ...
    @property
    def task_registry(self) -> TaskRegistryProtocol: ...
    @property
    def task_proxy_timeout_seconds(self) -> float | None: ...
    @property
    def model_information_service(self) -> ModelInformationServiceProtocol | None: ...
    @property
    def utility_tools(self) -> MCPUtilityToolsSurfaceProtocol: ...

    database_plugins: DatabasePluginsProtocol

    async def start(self) -> None: ...
    async def shutdown(self) -> None: ...
    def list_registered_prompt_names(self) -> list[str]: ...
    def plugin_tool_definitions(self) -> dict[str, JSONDict]: ...
    async def handle_mcp_request(
        self,
        request_data: JSONDict,
        client_id: str,
        session_id: str | None = None,
        protocol_version: str | None = None,
    ) -> JSONDict: ...
    @override
    async def execute_openai_tool_call(
        self,
        tool_name: str,
        arguments: JSONDict,
        *,
        request_context: RequestContext,
        user_id: int,
        conv_id: str,
        call_id: str,
        storage_call_id: str,
        message_index: int,
        assistant_at_ms: int,
        assistant_turn_at_ms: int,
        model_variant_index: int,
        sequence_index: int,
        content_index_before: int,
        thinking_index_before: int,
    ) -> JSONValue: ...
    async def cancel_openai_shell_sessions(self, *, user_id: int, conv_id: str) -> int: ...
    async def cancel_user_shell_sessions(self, *, user_id: int) -> int: ...
    async def notify_resource_updated(self, uri: str) -> None: ...

    def schedule_background_task(
        self,
        coro: Coroutine[None, None, None],
        *,
        name: str,
    ) -> asyncio.Task[None]: ...
    @override
    def track_background_task(self, task: asyncio.Task[None]) -> None: ...


class MCPWebFetcherProtocol(Protocol):
    adblock_service: EasyListAdblockServiceProtocol | None

    async def fetch_raw(
        self,
        url: str,
        *,
        offline_source: str | None = None,
        max_redirects: int = 10,
        progress_callback: Callable[[int, int | None, str], None | Awaitable[None]] | None = None,
    ) -> tuple[bytes, str, str, str | None]: ...


class MCPRemoteProtocol(MCPRemoteHostProtocol, Protocol):
    def attach_server(self, server: MCPServerProtocol) -> None: ...
    async def connect_to_server(self, config: MCPServerConfigProtocol) -> bool: ...
    async def connect_to_server_by_id(self, server_id: str) -> bool: ...
    async def start(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_host_roots(self) -> list[JSONDict]: ...
    async def set_host_roots(self, roots: list[JSONValue]) -> list[JSONDict]: ...
    async def list_connected_servers(self) -> list[JSONDict]: ...
    async def tool_catalog_version(self) -> str: ...
    async def list_all_tools(self) -> list[JSONDict]: ...
    async def list_all_resources(self) -> list[JSONDict]: ...
    async def list_all_prompts(self) -> list[JSONDict]: ...

    async def invoke_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: JSONDict,
    ) -> JSONDict: ...
    async def read_resource(self, server_id: str, uri: str) -> JSONDict: ...
    async def add_server(self, request: AddMCPServerRequest) -> MCPServerConfigProtocol: ...
    async def update_cached_server_config(self, config: MCPServerConfigProtocol) -> None: ...
    async def remove_server(self, server_id: str) -> bool: ...
    async def disconnect_from_server(self, server_id: str) -> bool: ...

    async def start_oauth_authorization(
        self,
        *,
        server_id: str,
        user_id: int,
    ) -> JSONDict: ...

    async def complete_oauth_callback(
        self,
        *,
        code: str,
        state_token: str,
        user_id: int,
    ) -> JSONDict: ...
    def build_oauth_client_metadata_document(self) -> JSONDict: ...


class MCPServicesCoordinatorProtocol(Protocol):
    @property
    def server(self) -> MCPServerProtocol: ...
    @property
    def remote(self) -> MCPRemoteProtocol: ...
    async def start(self) -> None: ...
    async def shutdown(self) -> None: ...
    @property
    def shutdown_event(self) -> asyncio.Event: ...
