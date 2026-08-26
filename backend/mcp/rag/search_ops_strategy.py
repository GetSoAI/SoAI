"""SoAI - MCP RAG search retrieval strategy execution [backend/mcp/rag/search_ops_strategy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from mcp.rag.configuration import get_rag_config_metadata
from mcp.rag.hybrid_search.hybrid_search import hybrid_search
from mcp.rag.mmr_reranking import maybe_rerank_mmr_results
from mcp.rag.search_similarity import run_similarity_search
from mcp.storage.search_operations import mmr_search

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol

__all__ = ("run_search_strategy",)

OPERATION = "mcp.rag.search_ops.rerank_results.mmr"


async def run_search_strategy(
    *,
    self: MCPRAGInternalProtocol,
    logger: LoggerProtocol,
    conv_id: str,
    query: str,
    query_vector: list[float],
    top_k: int,
    similarity_threshold: float,
    retrieval_strategy: str,
    user_id: int,
) -> JSONDict:
    if retrieval_strategy == "hybrid":
        return await hybrid_search(
            self,
            conv_id,
            query,
            top_k,
            similarity_threshold,
            user_id=user_id,
            _from_search=True,
            _query_embedding=query_vector,
        )
    if retrieval_strategy == "mmr":
        mmr_result = await mmr_search(
            self.storage,
            conv_id,
            query,
            query_vector,
            top_k,
            similarity_threshold,
        )
        rerank_config = await get_rag_config_metadata(self, conv_id)
        await maybe_rerank_mmr_results(
            runtime_flags=self.mcp_search.runtime_flags,
            logger=logger,
            query=query,
            mmr_result=mmr_result,
            rerank_config=rerank_config,
            operation=OPERATION,
            details={"conv_id": conv_id},
            failure_message="Reranking failed; returning un-reranked results (non-critical).",
        )
        return mmr_result
    return await run_similarity_search(
        self,
        logger,
        conv_id,
        query,
        query_vector,
        top_k,
        similarity_threshold,
    )
