"""SoAI - Authorization helpers for MCP RAG tools [backend/mcp/handlers/tools/authorization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.mcp.protocols_rag import MCPRAGProtocol
from mcp.auth import resolve_with_auth_errors
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("RAGAuthorizationContext",)


@dataclass(frozen=True, slots=True)
class RAGAuthorizationContext:
    rag: MCPRAGProtocol
    require_authenticated_user_id: Callable[[str], int]
    get_session_identity: Callable[[], tuple[int, str | None]] | None = None
    resolve_with_auth: Callable[[Awaitable[JSONValue]], Awaitable[JSONValue]] | None = None

    async def authorize_conversation(
        self,
        arguments: JSONDict,
        *,
        operation_label: str,
        authorization_operation: str,
    ) -> tuple[str, int]:
        operation_label = f"{operation_label} ({authorization_operation})"
        user_id = self.require_authenticated_user_id(operation_label)
        session_conv_id: str | None = None
        if self.get_session_identity is not None:
            _, raw_session_conv_id = self.get_session_identity()
            if isinstance(raw_session_conv_id, str):
                candidate = raw_session_conv_id.strip()
                if candidate and not candidate.startswith("soai_"):
                    session_conv_id = candidate
        if session_conv_id is not None:
            conv_id = session_conv_id
        else:
            conv_id_arg = arguments.get("conv_id")
            if not isinstance(conv_id_arg, str) or not conv_id_arg.strip():
                if self.get_session_identity is None:
                    raise MCPJSONRPCError(-32602, "conv_id must be a non-empty string")
                raise MCPJSONRPCError(
                    -32602,
                    "No active conversation context for this MCP session",
                )
            conv_id = conv_id_arg.strip()
        try:
            resolve_conv_id = self.rag.resolve_conv_id_for_user
        except AttributeError as exception:
            raise MCPJSONRPCError(
                -32603,
                "RAG does not implement resolve_conv_id_for_user; authorization cannot proceed.",
            ) from exception
        resolved_id = await self._resolve_with_auth_errors(resolve_conv_id(conv_id, user_id))
        if not isinstance(resolved_id, str) or not resolved_id.strip():
            raise MCPJSONRPCError(-32603, "RAG conv_id resolution returned invalid response.")
        return (resolved_id.strip(), user_id)

    async def _resolve_with_auth_errors(self, coro: Awaitable[JSONValue]) -> JSONValue:
        if self.resolve_with_auth is not None:
            return await self.resolve_with_auth(coro)
        return await resolve_with_auth_errors(coro)
