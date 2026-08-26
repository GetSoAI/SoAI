"""SoAI - MCP RAG knowledge tool definition builders [backend/mcp/rag/tool_definitions_knowledge_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_id_list_schema, build_tool_annotation_flags
from core.rag.option_contracts import build_retrieval_strategy_property
from mcp.protocol.icons import ICON_LIST, ICON_SEARCH, ICON_SETTINGS
from mcp.rag.tool_schema import (
    ICON_REFRESH,
    build_tool,
    prop_conv_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_knowledge_config_get_tool",
    "build_knowledge_list_tool",
    "build_knowledge_reindex_tool",
    "build_knowledge_search_tool",
)


def build_knowledge_search_tool(*, rag_search_output_schema: JSONDict) -> JSONDict:
    return build_tool(
        title="Search Knowledge",
        icon_src=ICON_SEARCH,
        description="Perform semantic search across all items in the conversation's knowledge base (includes both local files and web content). Supports 'similarity', 'mmr' (diverse results), and 'hybrid' (dense + BM25) retrieval strategies.",
        input_properties={
            "conv_id": prop_conv_id(),
            "query": {"type": "string", "description": "Search query text"},
            "top_k": {
                "type": "integer",
                "description": "Number of top results to return (default 5)",
            },
            "similarity_threshold": {
                "type": "number",
                "description": "Minimum similarity score (0.0-1.0, default 0.3)",
            },
            "retrieval_strategy": build_retrieval_strategy_property(),
        },
        required=["query"],
        output_schema=rag_search_output_schema,
        annotations=build_tool_annotation_flags(read_only=True, idempotent=True),
    )


def build_knowledge_list_tool() -> JSONDict:
    return build_tool(
        title="List Knowledge",
        icon_src=ICON_LIST,
        description="List all items in the conversation's knowledge base with their processing status.",
        input_properties={
            "conv_id": prop_conv_id(),
            "limit": {
                "type": "integer",
                "description": "Maximum documents to return (default 100, max 500)",
            },
            "offset": {
                "type": "integer",
                "description": "Zero-based document offset for pagination",
            },
        },
        required=[],
        output_schema={
            "type": "object",
            "properties": {
                "documents": build_id_list_schema(
                    {
                        "filename": {"type": "string"},
                        "file_type": {"type": "string"},
                        "file_size_bytes": {"type": "integer"},
                        "status": {"type": "string"},
                        "status_details": {"type": "string"},
                        "processed_chunks": {"type": "integer"},
                        "total_chunks": {"type": "integer"},
                        "embedding_model": {"type": "string"},
                        "error_message": {"type": "string"},
                        "created_at": {"type": "integer"},
                    },
                ),
                "count": {"type": "integer"},
                "total_count": {"type": "integer"},
                "limit": {"type": "integer"},
                "offset": {"type": "integer"},
                "has_more": {"type": "boolean"},
            },
        },
        annotations=build_tool_annotation_flags(read_only=True, idempotent=True),
    )


def build_knowledge_config_get_tool() -> JSONDict:
    return build_tool(
        title="Get Knowledge Configuration",
        icon_src=ICON_SETTINGS,
        description="Get the knowledge base configuration for a conversation, including retrieval strategy, chunking, embedding model, and reranking settings.",
        input_properties={"conv_id": prop_conv_id()},
        required=[],
        output_schema={
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "retrieval_strategy": {"type": "string"},
                "top_k": {"type": "integer"},
                "similarity_threshold": {"type": "number"},
                "chunking_strategy": {"type": "string"},
                "chunk_size": {"type": "integer"},
                "chunk_overlap": {"type": "integer"},
                "embedding_model": {"type": "string"},
                "rerank_enabled": {"type": "boolean"},
                "rerank_provider": {"type": "string"},
                "rerank_model": {"type": "string"},
                "rerank_top_n": {"type": "integer"},
                "hybrid_semantic_weight": {"type": "number"},
                "hybrid_bm25_weight": {"type": "number"},
                "hybrid_candidate_multiplier": {"type": "integer"},
                "hybrid_similarity_threshold": {"type": "number"},
                "hybrid_min_semantic_score": {"type": "number"},
                "hybrid_min_bm25_score": {"type": "number"},
                "bm25_tokenizer": {"type": "string"},
                "bm25_stopwords": {"type": "string"},
            },
        },
        annotations=build_tool_annotation_flags(read_only=True, idempotent=True),
    )


def build_knowledge_reindex_tool() -> JSONDict:
    return build_tool(
        title="Reindex Knowledge",
        icon_src=ICON_REFRESH,
        description="Reindex a conversation's knowledge base with a new embedding model. Requires confirm=true. Queues a background task.",
        input_properties={
            "conv_id": prop_conv_id(),
            "new_embedding_model": {
                "type": "string",
                "description": "Embedding model to reindex with (must not be auto)",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to confirm destructive reindex",
            },
        },
        required=["new_embedding_model", "confirm"],
        output_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "task_id": {"type": "string"},
                "conv_id": {"type": "string"},
            },
        },
        annotations=build_tool_annotation_flags(destructive=True),
    )
