"""SoAI - Shared base for MCP RAG tool handlers [backend/mcp/handlers/tools/rag_tool_base.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.handlers.tools.authorization import RAGAuthorizationContext
from mcp.handlers.tools.dependencies import RAGToolHandlersDependencies

__all__ = ("RAGToolBase",)


class RAGToolBase:
    def __init__(self, deps: RAGToolHandlersDependencies) -> None:
        self._deps = deps
        self._auth = RAGAuthorizationContext(
            rag=deps.rag,
            require_authenticated_user_id=deps.require_authenticated_user_id,
            get_session_identity=deps.get_session_identity,
            resolve_with_auth=deps.resolve_with_auth_errors,
        )
