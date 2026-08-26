"""SoAI - Dependencies for MCP RAG tool handlers [backend/mcp/handlers/tools/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from mcp.rag.internal_protocols import MCPRAGInternalProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

    type AuthErrorResolverCallable = Callable[[Awaitable[JSONValue]], Awaitable[JSONValue]]

__all__ = ("RAGToolHandlersDependencies",)


@dataclass(frozen=True, slots=True)
class RAGToolHandlersDependencies:
    rag: MCPRAGInternalProtocol
    require_authenticated_user_id: Callable[[str], int]
    get_session_identity: Callable[[], tuple[int, str | None]] | None = None
    resolve_with_auth_errors: AuthErrorResolverCallable | None = None

    def __post_init__(self) -> None:
        require_dependencies(
            owner="RAGToolHandlersDependencies",
            rag=self.rag,
            require_authenticated_user_id=self.require_authenticated_user_id,
        )
