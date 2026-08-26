"""SoAI - MCP RAG get config tool handler [backend/mcp/handlers/tools/knowledge_config_get.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.handlers.tools.inputs import rag_config_defaults
from mcp.handlers.tools.knowledge_config_result import (
    build_knowledge_config_result,
)
from mcp.handlers.tools.rag_tool_base import RAGToolBase

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("KnowledgeConfigGetTool",)


class KnowledgeConfigGetTool(RAGToolBase):
    async def __call__(self, arguments: JSONDict) -> JSONDict:
        conv_id, _ = await self._auth.authorize_conversation(
            arguments,
            operation_label="RAG get_config",
            authorization_operation="get_config",
        )
        config = rag_config_defaults(self._deps.rag)
        return build_knowledge_config_result(
            defaults=config,
            stored_raw=await self._deps.rag.database_files.get_rag_config(conv_id),
        )
