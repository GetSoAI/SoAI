"""SoAI - Document chunk storage with vector and sparse index [backend/mcp/storage/chunk_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.trace import get_logger
from core.types.json import JSONDict
from core.validation.requirements import require_nonempty_str
from mcp.rag.indexing.chunking import DocumentChunk
from mcp.storage.chunk_storage_chroma import (
    delete_chroma_vectors_under_lock,
    store_vectors_in_chromadb,
)
from mcp.storage.chunk_storage_persistence import persist_chunks_and_collection_metadata
from mcp.storage.chunk_storage_records import build_chunk_records
from mcp.storage.chunk_storage_reservations import (
    encoded_chroma_vector_payload_size,
    encoded_chunk_database_payload_size,
)
from mcp.storage.embedding_validation import validate_embeddings_shape
from mcp.storage.internal_protocols import MCPStorageProtocol

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = ("store_chunks_and_embeddings",)

LOGGER_NAME = "SoAI.mcp.storage.chunk_storage"
OPERATION = "mcp.storage.chunk_storage.cancel.rollback_vectors"


async def _rollback_chroma_after_failure(
    self: MCPStorageProtocol,
    *,
    conv_id: str,
    document_id: str,
    ids: list[str],
    primary_exception: BaseException,
) -> None:
    try:
        await uncancel_then_cleanup(delete_chroma_vectors_under_lock(self, conv_id, ids))
    except HANDLED_RUNTIME_EXCEPTIONS as rollback_error:
        primary_exception.add_note(f"Chroma rollback failed: {rollback_error}")
        log_exception(
            get_logger(LOGGER_NAME),
            rollback_error,
            message="Failed to rollback Chroma vectors after chunk storage failure.",
            operation=OPERATION,
            details={"conv_id": conv_id, "document_id": document_id},
            level="warning",
        )


async def store_chunks_and_embeddings(
    self: MCPStorageProtocol,
    conv_id: str,
    document_id: str,
    chunks: list[DocumentChunk],
    embeddings: list[list[float]],
    embedding_model: str,
    effective_model: str | None = None,
    token: CancellationTokenProtocol | None = None,
    job_id: str | None = None,
    lease_token: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not chunks:
        logger.warning(
            "No chunks to store for document %s in conversation %s",
            document_id,
            conv_id,
        )
        return
    embedding_dimensions = validate_embeddings_shape(embeddings, expected_count=len(chunks))
    effective_model_value = effective_model or embedding_model
    doc_info = await self.database_files.get_rag_document_by_id(document_id)
    doc_filename = str(doc_info.get("filename") or "") if isinstance(doc_info, dict) else ""
    doc_file_type = str(doc_info.get("file_type") or "") if isinstance(doc_info, dict) else ""
    doc_source_type = str(doc_info.get("source_type") or "") if isinstance(doc_info, dict) else ""
    doc_source_url = str(doc_info.get("source_url") or "") if isinstance(doc_info, dict) else ""
    chunk_records = build_chunk_records(document_id, chunks)
    ids = [
        require_nonempty_str(record.get("id"), field="chunk_record.id") for record in chunk_records
    ]
    metadatas: list[JSONDict] = [
        {
            "document_id": document_id,
            "chunk_index": chunk.index,
            "token_count": chunk.token_count,
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "filename": doc_filename,
            "file_type": doc_file_type,
            "source_type": doc_source_type,
            "source_url": doc_source_url,
        }
        for chunk in chunks
    ]
    documents = [chunk.content for chunk in chunks]
    batch_size = self.config.get_int("TOOLS.RAG.CHROMA_ADD_BATCH_SIZE")
    if batch_size < 1:
        batch_size = 256
    batch_size = min(int(batch_size), 512)
    store_timeout_sec = self.config.get_int("TOOLS.RAG.CHROMA_ADD_TIMEOUT_SEC")
    if store_timeout_sec < 1:
        store_timeout_sec = 600
    cancel_wait_sec = self.config.get_int("TOOLS.RAG.CHROMA_ADD_CANCEL_WAIT_SEC")
    cancel_wait_sec = max(cancel_wait_sec, 0)
    chroma_bytes = encoded_chroma_vector_payload_size(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    database_bytes = encoded_chunk_database_payload_size(
        ids=ids,
        chunks=chunk_records,
        embedding_model=embedding_model,
        effective_model=effective_model_value,
        embedding_dimensions=embedding_dimensions,
    )
    with self.storage_manager.reserve_disk_space(
        path=self.chroma_path,
        required_bytes=chroma_bytes,
        operation="mcp.storage.chunk_storage.store_chunks.chroma",
        details={"conv_id": conv_id, "document_id": document_id},
    ) as storage_reservation:
        with self.storage_manager.reserve_disk_space_for_install_volume(
            required_bytes=database_bytes,
            operation="mcp.storage.chunk_storage.store_chunks.database",
            details={"conv_id": conv_id, "document_id": document_id},
        ) as database_reservation:
            chroma_lock = await self.get_chroma_rw_lock(conv_id)
            async with chroma_lock:
                with claim_reserved_write(storage_reservation, size_bytes=chroma_bytes):
                    try:
                        await store_vectors_in_chromadb(
                            self,
                            conv_id=conv_id,
                            document_id=document_id,
                            ids=ids,
                            embeddings=embeddings,
                            documents=documents,
                            metadatas=metadatas,
                            embedding_model=embedding_model,
                            effective_model=effective_model_value,
                            batch_size=batch_size,
                            store_timeout_sec=int(store_timeout_sec),
                            cancel_wait_sec=int(cancel_wait_sec),
                            token=token,
                        )
                    except (asyncio.CancelledError, TaskCancelledError) as exception:
                        await _rollback_chroma_after_failure(
                            self,
                            conv_id=conv_id,
                            document_id=document_id,
                            ids=list(ids),
                            primary_exception=exception,
                        )
                        raise
                    except HANDLED_RUNTIME_EXCEPTIONS as exception:
                        await _rollback_chroma_after_failure(
                            self,
                            conv_id=conv_id,
                            document_id=document_id,
                            ids=list(ids),
                            primary_exception=exception,
                        )
                        raise
                    try:
                        with claim_reserved_write(
                            database_reservation,
                            size_bytes=database_bytes,
                        ):
                            await persist_chunks_and_collection_metadata(
                                self,
                                conv_id=conv_id,
                                document_id=document_id,
                                chunk_records=chunk_records,
                                embedding_model=embedding_model,
                                embedding_dimensions=embedding_dimensions,
                                effective_model=effective_model_value,
                                job_id=job_id,
                                lease_token=lease_token,
                            )
                    except (asyncio.CancelledError, TaskCancelledError) as exception:
                        await _rollback_chroma_after_failure(
                            self,
                            conv_id=conv_id,
                            document_id=document_id,
                            ids=list(ids),
                            primary_exception=exception,
                        )
                        raise
                    except HANDLED_RUNTIME_EXCEPTIONS as exception:
                        await _rollback_chroma_after_failure(
                            self,
                            conv_id=conv_id,
                            document_id=document_id,
                            ids=list(ids),
                            primary_exception=exception,
                        )
                        raise
