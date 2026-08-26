"""SoAI - MCP worker chunk/embed/store processor [backend/mcp/worker/processors/chunk_embed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_rag import (
    MCP_RAG_COUNTER_CHUNKING_CHUNKS_CREATED,
    MCP_RAG_COUNTER_EMBEDDINGS_REQUESTS,
    MCP_RAG_TIMING_EMBEDDING_LATENCY_MS,
)
from core.timing.monotonic import monotonic_ms
from core.validation.strings import coerce_optional_trimmed_str
from mcp.rag.document_content_hash import compute_document_content_hash
from mcp.rag.indexing.chunking import DocumentChunk
from mcp.storage.chunk_storage import store_chunks_and_embeddings
from mcp.storage.embeddings import generate_embeddings
from mcp.storage.sparse_index import rebuild_sparse_index
from mcp.worker.metrics_reporting import (
    record_worker_metric_counter,
    record_worker_metric_timing,
)
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease
from mcp.worker.processors.chunk_embed_cache_reuse import try_reuse_embedding_cache
from mcp.worker.rag_document_status_flow import update_worker_rag_document_status

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = ("process_chunk_embed_store",)

OPERATION_MCP_WORKER_CHUNK_EMBED = "mcp.worker.processors.chunk_embed"
LOGGER_NAME = "SoAI.mcp.worker.chunk_embed"


async def process_chunk_embed_store(
    self: MCPWorkerProtocol,
    document_id: str,
    conv_id: str,
    content: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str | None,
    task_id: str,
    user_id: int,
    chunking_strategy: str = "token_based",
    token: CancellationTokenProtocol | None = None,
    job_id: str | None = None,
    lease_token: str | None = None,
    status_details: str | None = None,
) -> int:
    logger = get_logger(LOGGER_NAME)
    content_hash = compute_document_content_hash(content)
    normalized_embedding_model = coerce_optional_trimmed_str(embedding_model)
    await self.send_progress(task_id, 30, "Creating text chunks...")
    await _update_document_status(
        self,
        document_id=document_id,
        status="chunking",
        content_hash=content_hash,
        job_id=job_id,
        lease_token=lease_token,
        status_details=status_details,
    )
    if normalized_embedding_model is not None and normalized_embedding_model.lower() != "auto":
        reused = await try_reuse_embedding_cache(
            self,
            document_id=document_id,
            conv_id=conv_id,
            content_hash=content_hash,
            chunking_strategy=chunking_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=normalized_embedding_model,
            task_id=task_id,
            token=token,
            store_chunks_and_embeddings=store_chunks_and_embeddings,
            job_id=job_id,
            lease_token=lease_token,
            status_details=status_details,
        )
        if reused is not None:
            return reused
    chunks = await self.chunker.chunk(content, chunking_strategy, chunk_size, chunk_overlap)
    await self.check_cancellation(task_id, "post-chunking", token=token)
    filtered_chunks: list[DocumentChunk] = []
    for chunk in chunks:
        if chunk.content.strip():
            filtered_chunks.append(
                DocumentChunk(
                    index=len(filtered_chunks),
                    content=chunk.content,
                    token_count=chunk.token_count,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                ),
            )
    chunks = filtered_chunks
    if not chunks:
        raise ValidationError(
            "No chunks generated from document content",
            details={"rag_status_details": "unreadable"},
        )
    record_worker_metric_counter(
        self.metrics,
        logger,
        MCP_RAG_COUNTER_CHUNKING_CHUNKS_CREATED,
        operation=OPERATION_MCP_WORKER_CHUNK_EMBED,
        details={"document_id": document_id, "conv_id": conv_id},
        value=len(chunks),
    )
    await self.check_cancellation(task_id, "chunking", token=token)
    await self.send_progress(
        task_id,
        40,
        f"Chunking complete. {len(chunks)} chunks created. Generating embeddings...",
    )
    await _update_document_status(
        self,
        document_id=document_id,
        status="embedding",
        content_hash=content_hash,
        total_chunks=len(chunks),
        job_id=job_id,
        lease_token=lease_token,
        status_details=status_details,
    )
    chunk_texts = [chunk.content for chunk in chunks]
    record_worker_metric_counter(
        self.metrics,
        logger,
        MCP_RAG_COUNTER_EMBEDDINGS_REQUESTS,
        operation=OPERATION_MCP_WORKER_CHUNK_EMBED,
        details={"document_id": document_id, "conv_id": conv_id},
    )
    await self.check_cancellation(task_id, "pre-embedding", token=token)
    embed_start_ms = monotonic_ms()
    out_actual_model: list[str] = []
    embeddings = await generate_embeddings(
        self.storage,
        chunk_texts,
        conv_id,
        user_id=user_id,
        embedding_model=embedding_model,
        task_id=task_id,
        out_actual_model=out_actual_model,
        token=token,
        send_progress=self.send_progress,
        check_cancellation=self.check_cancellation,
    )
    record_worker_metric_timing(
        self.metrics,
        logger,
        MCP_RAG_TIMING_EMBEDDING_LATENCY_MS,
        operation=OPERATION_MCP_WORKER_CHUNK_EMBED,
        details={"document_id": document_id, "conv_id": conv_id},
        duration_ms=float(monotonic_ms() - embed_start_ms),
    )
    if len(embeddings) != len(chunks):
        raise ValidationError(
            f"Embeddings count mismatch: got {len(embeddings)}, expected {len(chunks)}",
        )
    effective_model = (
        out_actual_model[0] if out_actual_model else normalized_embedding_model or "auto"
    )
    await self.check_cancellation(task_id, "pre-storage", token=token)
    if job_id and lease_token:
        await renew_durable_processing_lease(self, job_id=job_id, lease_token=lease_token)
    await self.send_progress(task_id, 90, "Storing chunks in vector database...")
    await store_chunks_and_embeddings(
        self.storage,
        conv_id,
        document_id,
        chunks,
        embeddings,
        normalized_embedding_model or "auto",
        effective_model=effective_model,
        token=token,
        job_id=job_id,
        lease_token=lease_token,
    )
    await self.check_cancellation(task_id, "post-storage", token=token)
    await self.send_progress(task_id, 95, "Finalizing document processing...")
    await _update_document_status(
        self,
        document_id=document_id,
        status="completed",
        content_hash=content_hash,
        total_chunks=len(chunks),
        processed_chunks=len(chunks),
        embedding_model=normalized_embedding_model or "auto",
        effective_embedding_model=effective_model,
        embedding_dimensions=(len(embeddings[0]) if embeddings and embeddings[0] else 0),
        job_id=job_id,
        lease_token=lease_token,
        status_details=status_details,
    )
    await rebuild_sparse_index(self.storage, conv_id)
    return len(chunks)


async def _update_document_status(
    worker: MCPWorkerProtocol,
    *,
    document_id: str,
    status: str,
    job_id: str | None,
    lease_token: str | None,
    content_hash: str | None = None,
    total_chunks: int | None = None,
    processed_chunks: int | None = None,
    embedding_model: str | None = None,
    effective_embedding_model: str | None = None,
    embedding_dimensions: int | None = None,
    status_details: str | None = None,
) -> None:
    await update_worker_rag_document_status(
        worker,
        document_id=document_id,
        status=status,
        job_id=job_id,
        lease_token=lease_token,
        content_hash=content_hash,
        total_chunks=total_chunks,
        processed_chunks=processed_chunks,
        embedding_model=embedding_model,
        effective_embedding_model=effective_embedding_model,
        embedding_dimensions=embedding_dimensions,
        status_details=status_details,
    )
