"""SoAI - MCP runtime/session protocol contracts [backend/core/mcp/protocols_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, Protocol

from core.events.protocols import EventBusProtocol
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol

if TYPE_CHECKING:
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

    type JSONRPCId = str | int | None
    type PromptHandler = Callable[[JSONDict], Awaitable[JSONDict]]

__all__ = (
    "MCPClientSessionProtocol",
    "MCPContextProtocol",
    "MCPPaginationProtocol",
    "MCPRemoteHostProtocol",
    "MCPSessionProtocol",
    "MCPStreamingProtocol",
    "MCPTaskProtocol",
)


class MCPClientSessionProtocol(Protocol):
    client_id: str
    session_id: str
    user_id: int
    conv_id: str | None
    protocol_version: str


class MCPRemoteHostProtocol(Protocol):
    @property
    def host_sampling_enabled(self) -> bool: ...

    @property
    def host_elicitation_enabled(self) -> bool: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    def normalize_roots(self) -> list[JSONDict]: ...

    async def send_host_mode_message(self, server_id: str, message: JSONDict) -> None: ...

    async def send_host_mode_request(
        self,
        server_id: str,
        method: str,
        parameters: JSONDict,
    ) -> JSONValue: ...

    async def record_pending_url_elicitation(
        self,
        server_id: str,
        elicitation_id: str,
        task_id: str,
    ) -> None: ...

    def schedule_background_task(
        self,
        coro: Coroutine[None, None, None],
        *,
        name: str,
    ) -> asyncio.Task[None]: ...

    def track_background_task(self, task: asyncio.Task[None]) -> None: ...

    async def clear_pending_url_elicitation(self, client_id: str, elicitation_id: str) -> bool: ...

    async def clear_pending_url_elicitation_for_task(
        self,
        client_id: str,
        elicitation_id: str,
        task_id: str,
    ) -> bool: ...


class MCPSessionProtocol(Protocol):
    def generate_session_id(self) -> str: ...

    async def ensure_client_session(
        self,
        session_id: str,
        protocol_version: str | None = None,
        user_id: int = 0,
        create_if_missing: bool = True,
    ) -> str: ...

    async def has_client_session(self, session_id: str) -> bool: ...

    async def close_client_session(self, session_id: str) -> None: ...

    async def close_all_client_sessions(self) -> None: ...

    def get_session_user_id(self, session_id: str) -> int: ...

    def resolve_session_id(self, client_id: str) -> str: ...

    def get_session(self, session_id: str | None) -> MCPClientSessionProtocol | None: ...

    async def update_session_activity(self, session_id: str) -> None: ...

    async def close_inactive_sessions(self) -> None: ...

    async def session_cleanup_loop(self, sweep_interval_sec: int) -> None: ...


class MCPStreamingProtocol(Protocol):
    async def has_active_client_stream(self, session_id: str) -> bool: ...

    async def sync_sse_event_counter_from_last_event_id(
        self,
        session_id: str,
        last_event_id: str | None,
    ) -> None: ...

    async def allocate_sse_event_id(self, session_id: str, payload: JSONDict) -> str: ...

    async def get_sse_replay_events(
        self,
        session_id: str,
        last_event_id: str | None,
    ) -> list[tuple[str, JSONDict]]: ...

    async def emit_client_stream_message(self, session_id: str, message: JSONDict) -> None: ...

    async def try_emit_client_stream_message(self, session_id: str, message: JSONDict) -> bool: ...

    def get_client_notification_stream(
        self,
        session_id: str,
        shutdown_events: tuple[asyncio.Event, ...] = (),
    ) -> AsyncGenerator[JSONDict | None]: ...


class MCPContextProtocol(Protocol):
    def set_active_client_context(self, client_id: str | None) -> contextvars.Token[str | None]: ...

    def reset_active_client_context(self, token: contextvars.Token[str | None]) -> None: ...

    def set_active_task_context(self, task_id: str | None) -> contextvars.Token[str | None]: ...

    def reset_active_task_context(self, token: contextvars.Token[str | None]) -> None: ...

    def set_active_user_id_context(self, user_id: int) -> contextvars.Token[int]: ...

    def reset_active_user_id_context(self, token: contextvars.Token[int]) -> None: ...

    def get_active_session(self) -> MCPClientSessionProtocol | None: ...

    def build_request_context(
        self,
        client_id: str,
        session_id: str | None,
        method: str,
        request_id: JSONRPCId,
    ) -> RequestContext: ...

    def current_session_identity(self) -> tuple[int, str | None]: ...

    def require_active_session(self) -> MCPClientSessionProtocol: ...

    def require_authenticated_user_id(self, operation: str = "") -> int: ...

    def resolve_rag_conv_id(self, conv_id: str | None, user_id: int) -> str | None: ...

    def validate_rag_user_id(self, user_id: int) -> None: ...

    def resolve_with_auth_errors(self, conv_id: str | None, user_id: int) -> tuple[str, int]: ...

    async def require_rag_user_authorization(
        self,
        conv_id: str,
        user_id: int,
        operation_label: str,
    ) -> tuple[str, int]: ...

    async def require_rag_document_authorization(
        self,
        document_id: str,
        user_id: int,
        operation_label: str,
    ) -> tuple[JSONDict, int]: ...


class MCPTaskProtocol(Protocol):
    def extract_task_id_parameter(self, parameters: JSONDict) -> str | None: ...

    def require_task_registry(self) -> TaskRegistryProtocol: ...

    def require_task_registry_queries(self) -> TaskRegistryQueryView: ...

    async def require_task_for_client(self, task_id: str, client_id: str) -> Task: ...

    def build_task_response(self, task: Task) -> JSONDict: ...

    async def get_task(self, task_id: str) -> Task | None: ...

    async def send_task_status_notification(self, task: Task) -> None: ...

    async def update_task_non_terminal_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str,
    ) -> None: ...

    async def complete_task(
        self,
        task_id: str,
        result: JSONDict,
        message: str | None = None,
    ) -> None: ...

    async def fail_task(self, task_id: str, code: int, message: str) -> None: ...

    async def cancel_task(self, task_id: str, reason: str) -> None: ...

    async def list_pending_host_interactions(self) -> list[JSONDict]: ...

    async def resolve_host_interaction(
        self,
        remote: MCPRemoteHostProtocol,
        task_id: str,
        action: str,
        content: JSONDict | None = None,
    ) -> JSONDict: ...


class MCPPaginationProtocol(Protocol):
    def encode_pagination_cursor(self, offset: int) -> str: ...

    def decode_pagination_cursor(self, cursor: str | None) -> int: ...

    def paginate_list[TItem](
        self,
        items: list[TItem],
        cursor: str | None,
    ) -> tuple[list[TItem], str | None]: ...
