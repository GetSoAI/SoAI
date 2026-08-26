"""SoAI - Embedding cache reuse for MCP chunk/embed/store [backend/mcp/worker/processors/chunk_embed_cache_reuse.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.rag_chunk_identity import build_rag_index_chunk_id
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import MCP_RAG_COUNTER_EMBEDDINGS_DEDUPLICATED
from mcp.rag.indexing.chunking import DocumentChunk
from mcp.storage.sparse_index import rebuild_sparse_index
from mcp.worker.metrics_reporting import record_worker_metric_counter
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease
from mcp.worker.rag_document_status_flow import update_worker_rag_document_status

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.concurrency.protocols import CancellationTokenProtocol
    from mcp.storage.internal_protocols import MCPStorageProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol

    type StoreChunksAndEmbeddingsCallable = Callable[
        [
            MCPStorageProtocol,
            str,
            str,
            list[DocumentChunk],
            list[list[float]],
            str,
            str | None,
            CancellationTokenProtocol | None,
            str | None,
            str | None,
        ],
        Awaitable[None],
    ]

__all__ = (
    "coerce_embedding_vector",
    "try_reuse_embedding_cache",
)

LOGGER_NAME = "SoAI.mcp.worker.chunk_embed_cache_reuse"
OPERATION = "mcp.worker.processors.chunk_embed.cache_reuse.store"


def coerce_embedding_vector(value: list[float] | list[int]) -> list[float] | None:
    if not value:
        return None
    out: list[float] = []
    for item in value:
        if isinstance(item, bool):
            return None
        out.append(float(item))
    return out or None


async def try_reuse_embedding_cache(
    self: MCPWorkerProtocol,
    *,
    document_id: str,
    conv_id: str,
    content_hash: str,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
    task_id: str,
    token: CancellationTokenProtocol | None,
    store_chunks_and_embeddings: StoreChunksAndEmbeddingsCallable,
    job_id: str | None,
    lease_token: str | None,
    status_details: str | None,
) -> int | None:
    logger = get_logger(LOGGER_NAME)
    cached = await self.database_files.find_completed_rag_document_for_embedding_cache(
        conv_id,
        content_hash,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
    )
    if not cached:
        return None
    cached_document_id = str(cached.get("id") or "").strip()
    if not cached_document_id or cached_document_id == document_id:
        return None
    cached_chunks = await self.database_files.get_rag_chunks_for_document(cached_document_id)
    if not cached_chunks:
        return None
    await self.send_progress(task_id, 40, "Cache hit. Reusing embeddings...")
    await update_worker_rag_document_status(
        self,
        document_id=document_id,
        status="embedding",
        job_id=job_id,
        lease_token=lease_token,
        content_hash=content_hash,
        total_chunks=len(cached_chunks),
        status_details=status_details,
    )
    cached_chunks_sorted = sorted(
        cached_chunks,
        key=lambda record: int(record.get("chunk_index") or 0),
    )
    chunks_from_cache: list[DocumentChunk] = []
    cached_ids: list[str] = []
    for record in cached_chunks_sorted:
        index_value = record.get("chunk_index")
        content_value = record.get("content")
        token_count_value = record.get("token_count")
        start_char_value = record.get("start_char")
        end_char_value = record.get("end_char")
        if not isinstance(index_value, int) or index_value < 0:
            return None
        if not isinstance(content_value, str) or not content_value.strip():
            return None
        if not isinstance(token_count_value, int) or token_count_value <= 0:
            return None
        start_char = (
            int(start_char_value)
            if isinstance(start_char_value, int) and start_char_value >= 0
            else 0
        )
        end_char = (
            int(end_char_value) if isinstance(end_char_value, int) and end_char_value >= 0 else 0
        )
        chunks_from_cache.append(
            DocumentChunk(
                index=index_value,
                content=content_value,
                token_count=token_count_value,
                start_char=start_char,
                end_char=end_char,
            ),
        )
        cached_ids.append(build_rag_index_chunk_id(cached_document_id, index_value))
    if not chunks_from_cache:
        return None
    rw_lock = await self.storage.get_chroma_rw_lock(conv_id)

    async with rw_lock.read_lock():
        collection_name = await self.storage.chroma.resolve_active_collection_name(conv_id)
        query_timeout = self.storage.config.get_int("TOOLS.RAG.CHROMA_QUERY_TIMEOUT_SEC")
        raw = await self.storage.chroma.get(
            conv_id=conv_id,
            collection_name=collection_name,
            ids=list(cached_ids),
            where=None,
            include=["embeddings"],
            timeout_sec=float(max(1, int(query_timeout))),
        )
    if not isinstance(raw, dict):
        logger.warning(
            "Embedding cache reuse failed: invalid ChromaDB get response for conversation %s",
            conv_id,
        )
        return None
    ids_value = raw.get("ids")
    embeddings_value = raw.get("embeddings")
    if not isinstance(ids_value, list) or not isinstance(embeddings_value, list):
        logger.warning(
            "Embedding cache reuse failed: unexpected ChromaDB get payload type for conversation %s",
            conv_id,
        )
        return None
    mapping: dict[str, list[float]] = {}
    for idx, returned_id in enumerate(ids_value):
        if not isinstance(returned_id, str) or not returned_id:
            continue
        if idx >= len(embeddings_value):
            continue
        candidate_embedding = embeddings_value[idx]
        if not isinstance(candidate_embedding, list):
            continue
        numeric_embedding: list[float] = []
        invalid_embedding = False
        for item in candidate_embedding:
            if isinstance(item, bool) or not isinstance(item, int | float):
                invalid_embedding = True
                break
            numeric_embedding.append(float(item))
        if invalid_embedding:
            continue
        vector = coerce_embedding_vector(numeric_embedding)
        if vector is None:
            continue
        mapping[returned_id] = vector
    ordered_embeddings: list[list[float]] = []
    for expected_id in cached_ids:
        vector = mapping.get(expected_id)
        if vector is None:
            logger.warning(
                "Embedding cache reuse failed: missing cached vectors for document %s in conversation %s",
                cached_document_id,
                conv_id,
            )
            return None
        ordered_embeddings.append(vector)
    try:
        if job_id and lease_token:
            await renew_durable_processing_lease(
                self,
                job_id=job_id,
                lease_token=lease_token,
            )
        await store_chunks_and_embeddings(
            self.storage,
            conv_id,
            document_id,
            chunks_from_cache,
            ordered_embeddings,
            embedding_model,
            embedding_model,
            token,
            job_id,
            lease_token,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced_exception = coerce_to_soai_error(
            exception,
            operation="mcp.worker.processors.chunk_embed.cache_reuse.store",
        )
        log_exception(
            logger,
            coerced_exception,
            message="Embedding cache reuse failed while storing reused chunks.",
            operation=OPERATION,
            details={
                "document_id": document_id,
                "conv_id": conv_id,
                "cached_document_id": cached_document_id,
            },
            level="warning",
        )
        return None
    await self.check_cancellation(task_id, "post-cache-storage", token=token)
    record_worker_metric_counter(
        self.metrics,
        logger,
        MCP_RAG_COUNTER_EMBEDDINGS_DEDUPLICATED,
        operation=OPERATION,
        details={"document_id": document_id, "conv_id": conv_id},
    )
    embedding_dimensions = (
        len(ordered_embeddings[0]) if ordered_embeddings and ordered_embeddings[0] else 0
    )
    await update_worker_rag_document_status(
        self,
        document_id=document_id,
        status="completed",
        job_id=job_id,
        lease_token=lease_token,
        content_hash=content_hash,
        total_chunks=len(chunks_from_cache),
        processed_chunks=len(chunks_from_cache),
        embedding_model=embedding_model,
        effective_embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        status_details=status_details,
    )
    await rebuild_sparse_index(self.storage, conv_id)
    return len(chunks_from_cache)
