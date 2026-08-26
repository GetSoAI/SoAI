"""SoAI - Web-fetch ingest document-scoped retrieval [backend/mcp/worker/processors/web_fetch_ingest_retrieval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.serialization.json import normalize_for_json
from core.types.json_value import require_json_dict
from core.validation.integers import is_strict_int
from core.validation.requirements import require_nonempty_str
from mcp.rag.configuration import get_rag_config_metadata
from mcp.rag.hybrid_search.hybrid_search import hybrid_search
from mcp.rag.mmr_reranking import maybe_rerank_mmr_results
from mcp.rag.reranking_policy import rerank_if_enabled
from mcp.storage.embeddings import generate_embeddings
from mcp.storage.search_operations import (
    chunk_metadata_fields,
    mmr_search,
    query_chroma_similarity_results,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("search_document_context",)

LOGGER_NAME = "SoAI.mcp.worker.web_fetch_ingest_retrieval"
OPERATION_MCP_WORKER_PROCESSORS_WEB_FETCH_INGEST_RETRIEVAL_SEARCH_DOCUMENT_CONTEXT_RERANK_MMR = (
    "mcp.worker.processors.web_fetch_ingest_retrieval.search_document_context.rerank_mmr"
)
OPERATION_MCP_WORKER_PROCESSORS_WEB_FETCH_INGEST_RETRIEVAL_SEARCH_SIMILARITY_RERANK = (
    "mcp.worker.processors.web_fetch_ingest_retrieval.search_similarity.rerank"
)


async def _search_similarity(
    worker: MCPWorkerProtocol,
    *,
    conv_id: str,
    document_id: str,
    query_embedding: list[float],
    query: str,
    top_k: int,
    similarity_threshold: float,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    filtered = await query_chroma_similarity_results(
        worker.storage,
        conv_id=conv_id,
        query_embedding=query_embedding,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        where_filter={"document_id": document_id},
        length_mismatch_error=ValidationError,
    )
    filtered = await rerank_if_enabled(
        context=worker,
        logger=logger,
        conv_id=conv_id,
        query=query,
        results=filtered,
        failure_log_message="Reranking failed for web-fetch ingest context; returning un-reranked results (non-critical).",
        operation=OPERATION_MCP_WORKER_PROCESSORS_WEB_FETCH_INGEST_RETRIEVAL_SEARCH_SIMILARITY_RERANK,
        failure_details={"conv_id": conv_id, "document_id": document_id},
    )
    return {"query": query, "results": filtered, "count": len(filtered)}


async def _fetch_document_overview_context(
    worker: MCPWorkerProtocol,
    *,
    conv_id: str,
    document_id: str,
    top_k: int,
) -> JSONDict:
    rw_lock = await worker.storage.get_chroma_rw_lock(conv_id)
    async with rw_lock.read_lock():
        collection_name = await worker.storage.chroma.resolve_active_collection_name(conv_id)
        query_timeout = worker.storage.config.get_int("TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC")
        raw_result = await worker.storage.chroma.get(
            conv_id=conv_id,
            collection_name=collection_name,
            ids=None,
            where={"document_id": document_id},
            include=["documents", "metadatas"],
            timeout_sec=float(max(1, int(query_timeout))),
        )
        normalized = normalize_for_json(raw_result)
        results = require_json_dict(normalized, label="chroma_get_result") if normalized else None
    if not results:
        return {"query": "", "results": [], "count": 0}
    documents_value = results.get("documents")
    metadatas_value = results.get("metadatas")
    documents = (
        [value for value in documents_value if isinstance(value, str)]
        if isinstance(documents_value, list)
        else []
    )
    metadatas = (
        [value for value in metadatas_value if isinstance(value, dict)]
        if isinstance(metadatas_value, list)
        else []
    )
    items_with_order: list[tuple[int, int, JSONDict]] = []
    count = min(len(documents), len(metadatas))
    for index in range(count):
        metadata = require_json_dict(metadatas[index], label="metadata")
        chunk_index_value = metadata.get("chunk_index")
        chunk_index = chunk_index_value if is_strict_int(chunk_index_value) else index
        items_with_order.append(
            (
                chunk_index,
                index,
                {
                    "content": require_nonempty_str(documents[index], field="document"),
                    **chunk_metadata_fields(metadata),
                },
            ),
        )
    items_with_order.sort(key=lambda item: (item[0], item[1]))
    selected = [item[2] for item in items_with_order[:top_k]]
    return {"query": "", "results": selected, "count": len(selected)}


async def search_document_context(
    worker: MCPWorkerProtocol,
    *,
    conv_id: str,
    document_id: str,
    query: str,
    top_k: int,
    similarity_threshold: float,
    retrieval_strategy: str,
    user_id: int,
    embedding_model: str,
    task_id: str,
    token: CancellationTokenProtocol | None,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    normalized_query = query.strip()
    if not normalized_query:
        return await _fetch_document_overview_context(
            worker,
            conv_id=conv_id,
            document_id=document_id,
            top_k=top_k,
        )
    query_embedding = await generate_embeddings(
        worker.storage,
        [normalized_query],
        conv_id,
        user_id=user_id,
        embedding_model=embedding_model,
        task_id=task_id,
        token=token,
        check_cancellation=worker.check_cancellation,
    )
    if not query_embedding or not query_embedding[0]:
        return {"query": normalized_query, "results": [], "count": 0}
    embedding = query_embedding[0]
    if retrieval_strategy == "hybrid":
        return await hybrid_search(
            worker,
            conv_id,
            normalized_query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            user_id=user_id,
            document_id=document_id,
            _from_search=True,
            _query_embedding=embedding,
        )
    if retrieval_strategy == "mmr":
        mmr_result = await mmr_search(
            worker.storage,
            conv_id,
            normalized_query,
            embedding,
            top_k,
            similarity_threshold,
            document_id=document_id,
        )
        rerank_config = await get_rag_config_metadata(worker, conv_id)
        await maybe_rerank_mmr_results(
            runtime_flags=worker.mcp_search.runtime_flags,
            logger=logger,
            query=normalized_query,
            mmr_result=mmr_result,
            rerank_config=rerank_config,
            operation=OPERATION_MCP_WORKER_PROCESSORS_WEB_FETCH_INGEST_RETRIEVAL_SEARCH_DOCUMENT_CONTEXT_RERANK_MMR,
            details={"conv_id": conv_id, "document_id": document_id},
            failure_message=(
                "Reranking failed for web-fetch ingest context; returning un-reranked MMR results (non-critical)."
            ),
        )
        mmr_results_value = mmr_result.get("results")
        if isinstance(mmr_results_value, list):
            mmr_result["count"] = len(mmr_results_value)
        return mmr_result
    return await _search_similarity(
        worker,
        conv_id=conv_id,
        document_id=document_id,
        query_embedding=embedding,
        query=normalized_query,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
