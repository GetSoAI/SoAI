"""SoAI - MCP RAG search tool handler [backend/mcp/handlers/tools/knowledge_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from mcp.handlers.tools.knowledge_guidance import (
    require_knowledge_search_sources_for_operation,
)
from mcp.handlers.tools.rag_tool_base import RAGToolBase
from mcp.handlers.tools.retrieval_params import resolve_retrieval_params
from mcp.protocol.types import MCPJSONRPCError
from mcp.shared.protocol_arguments import get_required_str

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("KnowledgeSearchTool",)


class KnowledgeSearchTool(RAGToolBase):
    async def __call__(self, arguments: JSONDict) -> JSONDict:
        conv_id, user_id = await self._auth.authorize_conversation(
            arguments,
            operation_label="RAG search",
            authorization_operation="search",
        )
        await require_knowledge_search_sources_for_operation(
            rag=self._deps.rag,
            conv_id=conv_id,
            user_id=user_id,
        )
        try:
            retrieval_params = await resolve_retrieval_params(
                rag=self._deps.rag,
                conv_id=conv_id,
                arguments=arguments,
            )
            return await self._deps.rag.search(
                conv_id=conv_id,
                query=get_required_str(arguments, "query"),
                top_k=retrieval_params.top_k,
                similarity_threshold=retrieval_params.similarity_threshold,
                retrieval_strategy=retrieval_params.retrieval_strategy,
                user_id=user_id,
            )
        except ValueError as exception:
            raise MCPJSONRPCError(-32602, str(exception)) from exception
        except ValidationError as exception:
            message = str(exception).strip() or "RAG search failed"
            normalized = message.lower()
            if "embedding" in normalized and (
                "capability" in normalized
                or "not available" in normalized
                or "no " in normalized
                or "missing" in normalized
            ):
                raise MCPJSONRPCError(
                    -32603,
                    "Embeddings are not available for knowledge_search. Configure at least one embeddings-capable backend/provider and retry.",
                ) from exception
            raise MCPJSONRPCError(-32603, message) from exception
