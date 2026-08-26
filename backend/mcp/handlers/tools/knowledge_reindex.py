"""SoAI - MCP RAG reindex tool handler [backend/mcp/handlers/tools/knowledge_reindex.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import is_auto_embedding_model_selector
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from mcp.handlers.tools.knowledge_guidance import (
    require_knowledge_documents_for_operation,
)
from mcp.handlers.tools.rag_tool_base import RAGToolBase
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("KnowledgeReindexTool",)


class KnowledgeReindexTool(RAGToolBase):
    async def __call__(self, arguments: JSONDict) -> JSONDict:
        conv_id, user_id = await self._auth.authorize_conversation(
            arguments,
            operation_label="RAG reindex",
            authorization_operation="reindex",
        )
        await require_knowledge_documents_for_operation(
            rag=self._deps.rag,
            conv_id=conv_id,
            require_searchable=False,
        )
        confirm = arguments.get("confirm")
        if confirm is not True:
            raise MCPJSONRPCError(-32602, "confirm must be true to start a reindex operation")
        raw_model_id = arguments.get("new_embedding_model")
        new_model = coerce_optional_trimmed_str(
            raw_model_id if isinstance(raw_model_id, str) else None,
        )
        if new_model is None:
            raise MCPJSONRPCError(-32602, "new_embedding_model must be a non-empty string")
        if is_auto_embedding_model_selector(new_model):
            raise MCPJSONRPCError(-32602, "new_embedding_model must not be 'auto' for reindex")
        try:
            reindex_result = await self._deps.rag.reindex_conversation(conv_id, user_id, new_model)
        except ValueError as exception:
            raise MCPJSONRPCError(-32602, str(exception)) from exception
        task_id = coerce_optional_trimmed_str(
            (
                reindex_result.get("task_id")
                if isinstance(reindex_result.get("task_id"), str)
                else None
            ),
        )
        knowledge_attachment = coerce_json_dict(reindex_result.get("knowledge_attachment"))
        if task_id is None or knowledge_attachment is None:
            raise MCPJSONRPCError(-32603, "RAG reindex did not return a valid task payload")
        return {
            "status": "queued",
            "task_id": task_id,
            "conv_id": conv_id,
            "knowledge_attachment": knowledge_attachment,
        }
