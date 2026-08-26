"""SoAI - MCP RAG tool handler registry builder [backend/mcp/handlers/tools/builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from mcp.handlers.tools.dependencies import RAGToolHandlersDependencies
from mcp.handlers.tools.knowledge_config_get import KnowledgeConfigGetTool
from mcp.handlers.tools.knowledge_list import KnowledgeListTool
from mcp.handlers.tools.knowledge_reindex import KnowledgeReindexTool
from mcp.handlers.tools.knowledge_search import KnowledgeSearchTool
from mcp.handlers.tools.knowledge_web_fetch import WebFetchKnowledgeTool
from mcp.handlers.tools.web_fetch import WebFetchTool
from mcp.rag.internal_protocols import MCPRAGInternalProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_mcp_rag_tool_handlers",)


def build_mcp_rag_tool_handlers(
    rag: MCPRAGInternalProtocol,
    *,
    require_authenticated_user_id: Callable[[str], int],
    get_session_identity: Callable[[], tuple[int, str | None]] | None = None,
) -> dict[str, Callable[[JSONDict], Awaitable[JSONDict]]]:
    deps = RAGToolHandlersDependencies(
        rag=rag,
        require_authenticated_user_id=require_authenticated_user_id,
        get_session_identity=get_session_identity,
    )
    knowledge_search: Callable[[JSONDict], Awaitable[JSONDict]] = KnowledgeSearchTool(deps)
    knowledge_list: Callable[[JSONDict], Awaitable[JSONDict]] = KnowledgeListTool(deps)
    knowledge_config_get: Callable[[JSONDict], Awaitable[JSONDict]] = KnowledgeConfigGetTool(deps)
    web_fetch: Callable[[JSONDict], Awaitable[JSONDict]] = WebFetchTool(deps)
    knowledge_web_fetch: Callable[[JSONDict], Awaitable[JSONDict]] = WebFetchKnowledgeTool(deps)
    knowledge_reindex: Callable[[JSONDict], Awaitable[JSONDict]] = KnowledgeReindexTool(deps)
    return {
        "knowledge_search": knowledge_search,
        "knowledge_list": knowledge_list,
        "knowledge_config_get": knowledge_config_get,
        "web_fetch": web_fetch,
        "knowledge_web_fetch": knowledge_web_fetch,
        "knowledge_reindex": knowledge_reindex,
    }
