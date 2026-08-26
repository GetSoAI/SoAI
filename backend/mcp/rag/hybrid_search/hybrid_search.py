"""SoAI - Hybrid search combining semantic and BM25 retrieval [backend/mcp/rag/hybrid_search/hybrid_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_mcp import RAGSearchCompletedEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_SEARCHES_HYBRID,
    MCP_RAG_COUNTER_SEARCHES_TOTAL,
    MCP_RAG_TIMING_SEARCH_LATENCY_MS,
)
from core.rag.config_metadata import (
    NormalizedRAGConfigMetadata,
    normalize_rag_config_metadata,
)
from core.rag.parameter_validation import (
    validate_non_negative_finite_float,
    validate_similarity_threshold,
    validate_top_k,
)
from core.timing.monotonic import monotonic_ms
from core.types.json_value import filter_json_mapping, require_json_dict
from core.validation.requirements import require_nonempty_str
from mcp.rag.configuration import get_rag_config_metadata
from mcp.rag.hybrid_search.bm25_only_chunks import fetch_bm25_only_chunks
from mcp.rag.hybrid_search.scoring import build_final_results, combine_semantic_and_bm25
from mcp.rag.hybrid_search.semantic_query import run_semantic_query
from mcp.storage.embeddings import generate_embeddings
from mcp.storage.reranking import rerank_results
from mcp.storage.search_operations import chunk_metadata_fields
from mcp.storage.sparse_index import sparse_search

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.rag.internal_protocols import MCPRAGSearchContextProtocol

__all__ = ("hybrid_search",)

LOGGER_NAME = "SoAI.mcp.rag.hybrid_search"
OPERATION_MCP_RAG_SEARCH_HYBRID_PUBLISH_COMPLETED_EVENT = (
    "mcp.rag.search_hybrid.publish_completed_event"
)
OPERATION_MCP_RAG_SEARCH_HYBRID_RERANK_RESULTS = "mcp.rag.search_hybrid.rerank_results"


def _metadata_has_configured_value(metadata: JSONDict, key: str) -> bool:
    raw = metadata.get(key)
    return raw is not None and not (isinstance(raw, str) and not raw.strip())


async def hybrid_search(
    self: MCPRAGSearchContextProtocol,
    conv_id: str,
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.2,
    bm25_weight: float = 0.3,
    semantic_weight: float = 0.7,
    user_id: int = 0,
    document_id: str | None = None,
    _from_search: bool = False,
    _query_embedding: list[float] | None = None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    top_k = validate_top_k(top_k)
    similarity_threshold = validate_similarity_threshold(similarity_threshold)
    bm25_weight = validate_non_negative_finite_float(
        bm25_weight,
        field_name="hybrid_bm25_weight",
    )
    semantic_weight = validate_non_negative_finite_float(
        semantic_weight,
        field_name="hybrid_semantic_weight",
    )
    if not _from_search and self.metrics is not None:
        self.metrics.increment_counter(*MCP_RAG_COUNTER_SEARCHES_TOTAL)
        self.metrics.increment_counter(*MCP_RAG_COUNTER_SEARCHES_HYBRID)
    start_time_ms = monotonic_ms() if not _from_search else None
    query_embedding = _query_embedding
    if query_embedding is None:
        generated = await generate_embeddings(self.storage, [query], conv_id, user_id=user_id)
        query_embedding = generated[0] if generated and generated[0] else []
    if not query_embedding:
        return {"query": query, "results": [], "count": 0}
    raw_metadata = await get_rag_config_metadata(self, conv_id)
    metadata: NormalizedRAGConfigMetadata = normalize_rag_config_metadata(raw_metadata)
    rerank_config = filter_json_mapping({**raw_metadata, **metadata})
    candidate_multiplier = metadata["hybrid_candidate_multiplier"]
    if _metadata_has_configured_value(raw_metadata, "hybrid_semantic_weight"):
        semantic_weight = metadata["hybrid_semantic_weight"]
    if _metadata_has_configured_value(raw_metadata, "hybrid_bm25_weight"):
        bm25_weight = metadata["hybrid_bm25_weight"]
    weight_sum = semantic_weight + bm25_weight
    if weight_sum <= 0:
        raise ValidationError("hybrid_semantic_weight + hybrid_bm25_weight must be > 0")
    semantic_weight = semantic_weight / weight_sum
    bm25_weight = bm25_weight / weight_sum
    if _metadata_has_configured_value(raw_metadata, "hybrid_similarity_threshold"):
        similarity_threshold = metadata["hybrid_similarity_threshold"]
    min_semantic_score = metadata["hybrid_min_semantic_score"]
    min_bm25_score = metadata["hybrid_min_bm25_score"]

    semantic_results = await run_semantic_query(
        self,
        conv_id=conv_id,
        query_embedding=query_embedding,
        top_k=top_k,
        candidate_multiplier=candidate_multiplier,
        document_id=document_id,
    )
    bm25_results = await sparse_search(
        self.storage,
        conv_id,
        query,
        top_k * candidate_multiplier,
        document_id=document_id,
    )
    bm25_scores: dict[str, float] = {}
    max_bm25 = max((score for _, score in bm25_results), default=1.0)
    for doc_id, score in bm25_results:
        bm25_scores[doc_id] = score / max_bm25 if max_bm25 > 0 else 0.0

    combined_scores = combine_semantic_and_bm25(
        semantic_results=semantic_results,
        bm25_scores=bm25_scores,
        min_semantic_score=min_semantic_score,
    )
    bm25_only_ids = [
        doc_id
        for doc_id, score in bm25_scores.items()
        if doc_id not in combined_scores and score >= min_bm25_score
    ]
    if bm25_only_ids:
        fetched_by_chunk_id = await fetch_bm25_only_chunks(self, bm25_only_ids)
        for chunk_id in bm25_only_ids:
            fetched = fetched_by_chunk_id.get(chunk_id)
            if fetched is None:
                continue
            metadata_value = fetched.get("metadata")
            chunk_metadata = require_json_dict(metadata_value, label="bm25_only_result.metadata")
            combined_scores[chunk_id] = {
                "content": require_nonempty_str(
                    fetched.get("content"),
                    field="bm25_only_result.content",
                ),
                "semantic_score": 0.0,
                "bm25_score": bm25_scores[chunk_id],
                **chunk_metadata_fields(chunk_metadata),
            }

    final_results = build_final_results(
        combined_scores=combined_scores,
        semantic_weight=semantic_weight,
        bm25_weight=bm25_weight,
        similarity_threshold=similarity_threshold,
        top_k=top_k,
    )
    if rerank_config.get("rerank_enabled") and final_results:
        try:
            final_results = await rerank_results(
                self.mcp_search.runtime_flags,
                query,
                final_results,
                rerank_config,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Reranking failed; returning un-reranked results (non-critical).",
                operation=OPERATION_MCP_RAG_SEARCH_HYBRID_RERANK_RESULTS,
                details={"conv_id": conv_id},
                level="debug",
            )
    if not _from_search:
        search_time_ms = max(0, monotonic_ms() - int(start_time_ms or 0))
        if self.metrics is not None:
            self.metrics.record_timing(
                *MCP_RAG_TIMING_SEARCH_LATENCY_MS,
                duration_ms=float(search_time_ms),
            )
        try:
            await self.event_bus.publish(
                RAGSearchCompletedEvent(
                    conv_id=conv_id,
                    query_length=len(query),
                    results_count=len(final_results),
                    retrieval_strategy="hybrid",
                    search_time_ms=int(search_time_ms),
                ),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to publish RAG hybrid search completed event (non-critical).",
                operation=OPERATION_MCP_RAG_SEARCH_HYBRID_PUBLISH_COMPLETED_EVENT,
                details={"conv_id": conv_id},
                level="debug",
            )
    return {"query": query, "results": final_results, "count": len(final_results)}
