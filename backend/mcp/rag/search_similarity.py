"""SoAI - MCP RAG similarity search path [backend/mcp/rag/search_similarity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from mcp.rag.reranking_policy import rerank_if_enabled
from mcp.storage.search_operations import query_chroma_similarity_results

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = ("run_similarity_search",)

OPERATION = "mcp.rag.search_ops.rerank_results.similarity"


async def run_similarity_search(
    rag: MCPRAGInternalProtocol,
    logger: LoggerProtocol,
    conv_id: str,
    query: str,
    query_embedding: list[float],
    top_k: int,
    similarity_threshold: float,
) -> JSONDict:
    filtered = await query_chroma_similarity_results(
        rag.storage,
        conv_id=conv_id,
        query_embedding=query_embedding,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        where_filter=None,
        length_mismatch_error=StateError,
    )
    filtered = await rerank_if_enabled(
        context=rag,
        logger=logger,
        conv_id=conv_id,
        query=query,
        results=filtered,
        failure_log_message="Reranking failed; returning un-reranked results (non-critical).",
        operation=OPERATION,
        failure_details={"conv_id": conv_id},
    )
    return {"query": query, "results": filtered, "count": len(filtered)}
