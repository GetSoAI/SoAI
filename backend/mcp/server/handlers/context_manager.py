"""SoAI - MCP server context and RAG authorization manager [backend/mcp/server/handlers/context_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.conversations.protocols_database_conversation_records import (
    DatabaseConversationsProtocol,
)
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.protocols import DatabaseFilesProtocol
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.types.json import is_json_dict
from core.types.json_value import is_json_value
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.protocol.types import JsonRpcId, MCPClientSession
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPContextManager",
    "MCPContextManagerDependencies",
)

LOGGER_NAME = "SoAI.mcp.server.context_manager"
OPERATION_MCP_SERVER_CONTEXT_REQUIRE_RAG_DOCUMENT_AUTHORIZATION = (
    "mcp.server.context.require_rag_document_authorization"
)
OPERATION_MCP_SERVER_CONTEXT_REQUIRE_RAG_USER_AUTHORIZATION = (
    "mcp.server.context.require_rag_user_authorization"
)


@dataclass(frozen=True, slots=True)
class MCPContextManagerDependencies:
    state: MCPServerState
    database_conversations: DatabaseConversationsProtocol
    database_files: DatabaseFilesProtocol
    active_client_context: contextvars.ContextVar[str | None]
    active_task_context: contextvars.ContextVar[str | None]
    active_user_id_context: contextvars.ContextVar[int]
    get_session: Callable[[str | None], MCPClientSession | None]
    get_session_user_id: Callable[[str], int]
    resolve_session_id: Callable[[str], str]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPContextManagerDependencies",
            active_client_context=self.active_client_context,
            active_task_context=self.active_task_context,
            active_user_id_context=self.active_user_id_context,
            database_conversations=self.database_conversations,
            database_files=self.database_files,
            get_session=self.get_session,
            get_session_user_id=self.get_session_user_id,
            resolve_session_id=self.resolve_session_id,
            state=self.state,
        )


class MCPContextManager:
    def __init__(self, deps: MCPContextManagerDependencies) -> None:
        self._state = deps.state
        self._database_conversations = deps.database_conversations
        self._database_files = deps.database_files
        self._active_client_context = deps.active_client_context
        self._active_task_context = deps.active_task_context
        self._active_user_id_context = deps.active_user_id_context
        self._get_session = deps.get_session
        self._get_session_user_id = deps.get_session_user_id
        self._resolve_session_id = deps.resolve_session_id

    def set_active_client_context(self, client_id: str | None) -> contextvars.Token[str | None]:
        if client_id is not None and not client_id.strip():
            raise ValidationError("client_id must be non-empty when provided.")
        return self._active_client_context.set(client_id)

    def reset_active_client_context(self, token: contextvars.Token[str | None]) -> None:
        if token is None:
            raise ValidationError("client context token is required.")
        self._active_client_context.reset(token)

    def set_active_task_context(self, task_id: str | None) -> contextvars.Token[str | None]:
        if task_id is not None and not task_id.strip():
            raise ValidationError("task_id must be non-empty when provided.")
        return self._active_task_context.set(task_id)

    def reset_active_task_context(self, token: contextvars.Token[str | None]) -> None:
        if token is None:
            raise ValidationError("task context token is required.")
        self._active_task_context.reset(token)

    def set_active_user_id_context(self, user_id: int) -> contextvars.Token[int]:
        return self._active_user_id_context.set(user_id)

    def reset_active_user_id_context(self, token: contextvars.Token[int]) -> None:
        if token is None:
            raise ValidationError("user_id context token is required.")
        self._active_user_id_context.reset(token)

    def get_active_session(self) -> MCPClientSession | None:
        client_id = self._active_client_context.get()
        if not client_id:
            return None
        session_id = self._resolve_session_id(client_id)
        return self._get_session(session_id)

    def build_request_context(
        self,
        client_id: str,
        session_id: str | None,
        method: str,
        request_id: JsonRpcId,
    ) -> RequestContext:
        trace_id = f"mcp:{client_id}:{method}:{request_id}"
        resolved_session_id = session_id or self._resolve_session_id(client_id)
        user_id = self._get_session_user_id(resolved_session_id)
        return RequestContext(
            trace_id=trace_id,
            cancellation_id=trace_id,
            user_id=user_id,
        )

    def current_session_identity(self) -> tuple[int, str | None]:
        session = self.get_active_session()
        if session is None:
            return (0, None)
        return (session.user_id, session.session_id)

    def require_active_session(self) -> MCPClientSession:
        session = self.get_active_session()
        if session is None:
            raise MCPJSONRPCError(-32603, "No active MCP session context")
        return session

    def require_authenticated_user_id(self, operation: str = "") -> int:
        session = self.require_active_session()
        if session.user_id == 0:
            message = (
                f"User authentication required for {operation}"
                if operation
                else "User authentication required"
            )
            raise MCPJSONRPCError(-32603, message)
        return session.user_id

    def resolve_rag_conv_id(self, conv_id: str | None, user_id: int) -> str | None:
        if conv_id:
            return conv_id
        session = self.get_active_session()
        if session is None:
            return None
        if user_id > 0 and session.user_id != user_id:
            return None
        return session.conv_id

    def validate_rag_user_id(self, user_id: int) -> None:
        if user_id == 0:
            raise MCPJSONRPCError(-32603, "RAG operations require authentication")

    def resolve_with_auth_errors(
        self,
        conv_id: str | None,
        user_id: int,
    ) -> tuple[str, int]:
        self.validate_rag_user_id(user_id)
        resolved = self.resolve_rag_conv_id(conv_id, user_id)
        if not resolved:
            raise MCPJSONRPCError(-32602, "conv_id is required")
        return (resolved, user_id)

    async def require_rag_user_authorization(
        self,
        conv_id: str,
        user_id: int,
        operation_label: str,
    ) -> tuple[str, int]:
        logger = get_logger(LOGGER_NAME)
        self.validate_rag_user_id(user_id)
        try:
            if not conv_id:
                raise MCPJSONRPCError(-32602, "conv_id is required")
            conversation = await self._database_conversations.get_conversation(conv_id, user_id)
            if conversation is None:
                raise MCPJSONRPCError(-32602, f"Conversation not found: {conv_id}")
            return (conv_id, user_id)
        except MCPJSONRPCError:
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to verify RAG user authorization",
                operation=OPERATION_MCP_SERVER_CONTEXT_REQUIRE_RAG_USER_AUTHORIZATION,
                details={"conv_id": conv_id, "user_id": user_id, "operation": operation_label},
            )
            raise MCPJSONRPCError(-32603, "Failed to verify authorization") from exception

    async def require_rag_document_authorization(
        self,
        document_id: str,
        user_id: int,
        operation_label: str,
    ) -> tuple[JSONDict, int]:
        logger = get_logger(LOGGER_NAME)
        self.validate_rag_user_id(user_id)
        try:
            if not document_id:
                raise MCPJSONRPCError(-32602, "document_id is required")
            document = await self._database_files.get_rag_document_by_id(document_id)
            if document is None:
                raise MCPJSONRPCError(-32602, f"Document not found: {document_id}")
            if document["user_id"] != user_id:
                raise MCPJSONRPCError(-32603, "Not authorized to access this document")
            document_json: JSONDict = {}
            for key, value in document.items():
                if is_json_value(value):
                    document_json[key] = value
            if not is_json_dict(document_json):
                raise MCPJSONRPCError(-32603, "Invalid document record")
            return (document_json, user_id)
        except MCPJSONRPCError:
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to verify RAG document authorization",
                operation=OPERATION_MCP_SERVER_CONTEXT_REQUIRE_RAG_DOCUMENT_AUTHORIZATION,
                details={
                    "document_id": document_id,
                    "user_id": user_id,
                    "operation": operation_label,
                },
            )
            raise MCPJSONRPCError(-32603, "Failed to verify authorization") from exception
