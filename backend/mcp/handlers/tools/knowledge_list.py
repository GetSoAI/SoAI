"""SoAI - MCP RAG list documents tool handler [backend/mcp/handlers/tools/knowledge_list.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json_value import is_json_value
from core.validation.coercion import coerce_int
from mcp.handlers.tools.knowledge_guidance import build_empty_knowledge_list_result
from mcp.handlers.tools.rag_tool_base import RAGToolBase

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("KnowledgeListTool",)

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 500


class KnowledgeListTool(RAGToolBase):
    async def __call__(self, arguments: JSONDict) -> JSONDict:
        conv_id, user_id = await self._auth.authorize_conversation(
            arguments,
            operation_label="RAG list_documents",
            authorization_operation="list_documents",
        )
        raw_counts = (
            await self._deps.rag.database_files.get_rag_counts_for_conversation_with_active_links(
                conv_id,
                user_id,
            )
        )
        if isinstance(raw_counts, dict) and raw_counts.get("document_count") == 0:
            return build_empty_knowledge_list_result()
        limit = coerce_int(arguments.get("limit")) or _DEFAULT_LIMIT
        limit = min(max(1, limit), _MAX_LIMIT)
        offset = coerce_int(arguments.get("offset")) or 0
        offset = max(0, offset)
        docs_value = await self._deps.rag.database_files.get_rag_documents_for_conversation_with_active_links(
            conv_id,
            user_id,
            offset=offset,
            limit=limit,
        )
        docs = (
            [
                {key: value for key, value in doc.items() if is_json_value(value)}
                for doc in docs_value
                if isinstance(doc, dict)
            ]
            if isinstance(docs_value, list)
            else []
        )
        total_count = (
            raw_counts.get("document_count") if isinstance(raw_counts, dict) else len(docs)
        )
        resolved_total_count = total_count if isinstance(total_count, int) else len(docs)
        return {
            "documents": docs,
            "count": len(docs),
            "total_count": resolved_total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(docs) < resolved_total_count,
        }
