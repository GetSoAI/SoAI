"""SoAI - Document embedding loop for reindex processor [backend/mcp/worker/processors/reindex_document_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.files.database_types import RAGConversationChunkPreview, RAGDocumentRecord
from core.hardware.reservation_claims import claim_reserved_write
from core.validation.coercion import coerce_int, coerce_json_value
from mcp.rag.maintenance_locks import renew_rag_maintenance_lease
from mcp.storage.chunk_storage_reservations import encoded_chroma_vector_payload_size
from mcp.storage.embedding_validation import validate_embeddings_shape
from mcp.storage.embeddings import generate_embeddings
from mcp.worker.processing.durable_job_runtime import renew_durable_processing_lease

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.types.json import JSONDict
    from mcp.worker.internal_protocols import MCPWorkerProtocol

__all__ = (
    "ReindexDocumentLoopConfig",
    "ReindexDocumentLoopResult",
    "process_documents_for_reindex",
)


@dataclass(frozen=True, slots=True)
class ReindexDocumentLoopConfig:
    conv_id: str
    embedding_model: str
    embedding_dimensions: int | None
    collection_name: str
    user_id: int
    task_id: str
    document_count: int
    job_id: str | None
    lease_token: str | None
    maintenance_lease_token: str


@dataclass(frozen=True, slots=True)
class ReindexDocumentLoopResult:
    total_chunks: int


async def process_documents_for_reindex(
    worker: MCPWorkerProtocol,
    config: ReindexDocumentLoopConfig,
    token: CancellationTokenProtocol | None = None,
) -> ReindexDocumentLoopResult:
    total_chunks = 0
    after_document_id: str | None = None
    after_chunk_index: int | None = None
    page_size = max(1, worker.storage.config.get_int("TOOLS.RAG.REINDEX_CHUNK_PAGE_SIZE"))
    page_size = min(page_size, 512)
    while True:
        await worker.check_cancellation(config.task_id, "reindex-chunk-page", token=token)
        await _renew_reindex_leases(worker, config)
        chunk_rows = await worker.database_files.get_rag_chunks_for_conversation_page(
            config.conv_id,
            after_document_id=after_document_id,
            after_chunk_index=after_chunk_index,
            limit=page_size,
        )
        if not chunk_rows:
            break
        last_row = chunk_rows[-1]
        next_document_id = str(last_row.get("document_id") or "").strip()
        next_chunk_index_value = last_row.get("chunk_index")
        next_chunk_index = (
            next_chunk_index_value if isinstance(next_chunk_index_value, int) else None
        )
        valid_rows = _filter_valid_chunks(chunk_rows)
        if not valid_rows:
            after_document_id = next_document_id
            after_chunk_index = next_chunk_index
            continue
        await _renew_reindex_leases(worker, config)
        chunk_texts = [str(chunk.get("content") or "") for chunk in valid_rows]
        await worker.send_progress(
            config.task_id,
            10 + min(60, int(total_chunks / max(1, config.document_count) * 10)),
            f"Embedding reindex chunk page starting at {total_chunks}...",
        )

        embeddings = await generate_embeddings(
            worker.storage,
            chunk_texts,
            config.conv_id,
            user_id=config.user_id,
            embedding_model=config.embedding_model,
            task_id=config.task_id,
            token=token,
            send_progress=worker.send_progress,
            check_cancellation=worker.check_cancellation,
        )
        await _renew_reindex_leases(worker, config)

        _validate_embeddings_count(embeddings, chunk_texts, "conversation")
        _validate_embedding_dimensions(embeddings, chunk_texts, config, "conversation")

        doc_infos = await _load_document_metadata(worker, valid_rows)
        ids, metadatas = _build_chunk_ids_and_metadata(valid_rows, doc_infos)
        _validate_payload_consistency(ids, chunk_texts, metadatas, "conversation")
        batch_size = worker.storage.config.get_int("TOOLS.RAG.CHROMA_ADD_BATCH_SIZE")
        if batch_size < 1:
            batch_size = 256
        batch_size = min(int(batch_size), 512)
        add_timeout = worker.storage.config.get_int("TOOLS.RAG.CHROMA_ADD_TIMEOUT_SEC")
        if add_timeout < 1:
            add_timeout = 600
        cancel_wait = worker.storage.config.get_int("TOOLS.RAG.CHROMA_ADD_CANCEL_WAIT_SEC")
        cancel_wait = max(0, int(cancel_wait))
        chroma_bytes = encoded_chroma_vector_payload_size(
            ids=ids,
            embeddings=embeddings,
            documents=chunk_texts,
            metadatas=metadatas,
        )
        with worker.storage.storage_manager.reserve_disk_space(
            path=worker.storage.chroma_path,
            required_bytes=chroma_bytes,
            operation="mcp.worker.reindex.document_loop.chroma",
            details={"conv_id": config.conv_id},
        ) as reservation:
            with claim_reserved_write(reservation, size_bytes=chroma_bytes):
                await worker.storage.chroma.add_upsert_ids(
                    conv_id=config.conv_id,
                    collection_name=config.collection_name,
                    ids=tuple(ids),
                    embeddings=tuple(embeddings),
                    documents=tuple(chunk_texts),
                    metadatas=tuple(metadatas),
                    batch_size=batch_size,
                    timeout_sec=float(int(add_timeout)),
                    cancel_wait_sec=float(cancel_wait),
                    token=token,
                )
        await _renew_reindex_leases(worker, config)
        total_chunks += len(ids)
        after_document_id = next_document_id
        after_chunk_index = next_chunk_index

    return ReindexDocumentLoopResult(total_chunks=total_chunks)


async def _renew_reindex_leases(
    worker: MCPWorkerProtocol,
    config: ReindexDocumentLoopConfig,
) -> None:
    if config.job_id and config.lease_token:
        await renew_durable_processing_lease(
            worker,
            job_id=config.job_id,
            lease_token=config.lease_token,
        )
    await renew_rag_maintenance_lease(
        database_files=worker.database_files,
        config=worker.config,
        conv_id=config.conv_id,
        lease_token=config.maintenance_lease_token,
        expired_message=f"Reindex maintenance lock expired for conversation {config.conv_id}",
    )


def _filter_valid_chunks(
    chunks: list[RAGConversationChunkPreview],
) -> list[RAGConversationChunkPreview]:
    return [chunk for chunk in chunks if str(chunk.get("content") or "")]


async def _load_document_metadata(
    worker: MCPWorkerProtocol,
    chunks: list[RAGConversationChunkPreview],
) -> dict[str, RAGDocumentRecord]:
    metadata: dict[str, RAGDocumentRecord] = {}
    for chunk in chunks:
        doc_id = str(chunk.get("document_id") or "").strip()
        if not doc_id or doc_id in metadata:
            continue
        doc_info = await worker.database_files.get_rag_document_by_id(doc_id)
        if doc_info is not None:
            metadata[doc_id] = doc_info
    return metadata


def _validate_embeddings_count(
    embeddings: list[list[float]],
    chunk_texts: list[str],
    doc_id: str,
) -> None:
    if len(embeddings) != len(chunk_texts):
        raise ValidationError(
            f"Embeddings count mismatch for {doc_id}: got {len(embeddings)}, expected {len(chunk_texts)}",
        )


def _validate_embedding_dimensions(
    embeddings: list[list[float]],
    chunk_texts: list[str],
    config: ReindexDocumentLoopConfig,
    doc_id: str,
) -> None:
    dims = validate_embeddings_shape(embeddings, expected_count=len(chunk_texts))
    if config.embedding_dimensions is not None:
        expected_dims = coerce_int(config.embedding_dimensions) or 0
        if expected_dims > 0 and dims != expected_dims:
            raise ValidationError(
                f"Embedding dimensions mismatch for {doc_id}: expected {expected_dims}, got {dims}",
            )


def _build_chunk_ids_and_metadata(
    chunk_rows: list[RAGConversationChunkPreview],
    doc_infos: dict[str, RAGDocumentRecord],
) -> tuple[list[str], list[JSONDict]]:
    ids: list[str] = []
    metadatas: list[JSONDict] = []

    for chunk in chunk_rows:
        doc_id = str(chunk.get("document_id") or "").strip()
        doc_info = doc_infos.get(doc_id)
        doc_filename = str(doc_info.get("filename") or "") if doc_info else ""
        doc_file_type = str(doc_info.get("file_type") or "") if doc_info else ""
        doc_source_type = str(doc_info.get("source_type") or "") if doc_info else ""
        doc_source_url = str(doc_info.get("source_url") or "") if doc_info else ""
        chunk_id = str(chunk.get("id") or "").strip()
        if not chunk_id:
            raise ValidationError(f"Chunk id missing during reindex for document {doc_id}")
        chunk_index = chunk.get("chunk_index")
        if not isinstance(chunk_index, int):
            chunk_index = len(ids)
        ids.append(chunk_id)
        metadatas.append(
            {
                "document_id": doc_id,
                "chunk_index": chunk_index,
                "token_count": coerce_json_value(chunk.get("token_count")),
                "start_char": coerce_json_value(chunk.get("start_char")),
                "end_char": coerce_json_value(chunk.get("end_char")),
                "filename": doc_filename,
                "file_type": doc_file_type,
                "source_type": doc_source_type,
                "source_url": doc_source_url,
            },
        )

    return ids, metadatas


def _validate_payload_consistency(
    ids: list[str],
    chunk_texts: list[str],
    metadatas: list[JSONDict],
    doc_id: str,
) -> None:
    if len(ids) != len(chunk_texts) or len(metadatas) != len(chunk_texts):
        raise ValidationError(
            f"Reindex payload mismatch for {doc_id}: ids={len(ids)} texts={len(chunk_texts)} metadatas={len(metadatas)}",
        )
    if len(set(ids)) != len(ids):
        raise ValidationError(f"Duplicate chunk ids detected during reindex for {doc_id}")
