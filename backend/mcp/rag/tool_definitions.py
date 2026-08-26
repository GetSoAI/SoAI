"""SoAI - MCP RAG tool schema definitions and builders [backend/mcp/rag/tool_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_search_results_schema
from mcp.rag.tool_definitions_knowledge_tools import (
    build_knowledge_config_get_tool,
    build_knowledge_list_tool,
    build_knowledge_reindex_tool,
    build_knowledge_search_tool,
)
from mcp.rag.tool_definitions_schemas import (
    build_fetch_result_properties,
    build_immediate_context_schema,
    build_ingest_limits_schema,
    build_output_limits_schema,
    build_rag_search_result_properties,
)
from mcp.rag.tool_definitions_web_tools import (
    build_knowledge_web_fetch_tool,
    build_web_fetch_tool,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_mcp_rag_tool_definitions",)


def build_mcp_rag_tool_definitions() -> dict[str, JSONDict]:
    rag_search_result_properties = build_rag_search_result_properties()
    rag_search_output_schema = build_search_results_schema(rag_search_result_properties)
    immediate_context_schema = build_immediate_context_schema(rag_search_result_properties)
    output_limits_schema = build_output_limits_schema()
    ingest_limits_schema = build_ingest_limits_schema()
    fetch_result_properties = build_fetch_result_properties(
        immediate_context_schema=immediate_context_schema,
        output_limits_schema=output_limits_schema,
        ingest_limits_schema=ingest_limits_schema,
    )
    return {
        "knowledge_search": build_knowledge_search_tool(
            rag_search_output_schema=rag_search_output_schema,
        ),
        "knowledge_list": build_knowledge_list_tool(),
        "web_fetch": build_web_fetch_tool(),
        "knowledge_web_fetch": build_knowledge_web_fetch_tool(
            fetch_result_properties=fetch_result_properties,
        ),
        "knowledge_config_get": build_knowledge_config_get_tool(),
        "knowledge_reindex": build_knowledge_reindex_tool(),
    }
