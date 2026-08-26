"""SoAI - Lock-scoped Chroma chunk vector mutations [backend/mcp/storage/chunk_storage_chroma.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from mcp.storage.chroma_collection_reservation import reserve_chroma_collection_metadata
from mcp.storage.chroma_metadata import coerce_chroma_metadata_list
from mcp.storage.internal_protocols import MCPStorageProtocol

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = ("delete_chroma_vectors_under_lock", "store_vectors_in_chromadb")

LOGGER_NAME = "SoAI.mcp.storage.chunk_storage_chroma"
OPERATION = "mcp.storage.chunk_storage.store_chunks.chroma_add"


async def store_vectors_in_chromadb(
    self: MCPStorageProtocol,
    *,
    conv_id: str,
    document_id: str,
    ids: Sequence[str],
    embeddings: Sequence[Sequence[float]],
    documents: Sequence[str],
    metadatas: Sequence[JSONDict],
    embedding_model: str,
    effective_model: str,
    batch_size: int,
    store_timeout_sec: int,
    cancel_wait_sec: int,
    token: CancellationTokenProtocol | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    chroma_metadatas = coerce_chroma_metadata_list(list(metadatas), field="metadatas")
    try:
        collection_name = await self.chroma.resolve_active_collection_name(conv_id)
        with reserve_chroma_collection_metadata(
            self.storage_manager,
            chroma_path=self.chroma_path,
            operation="mcp.storage.chunk_storage.ensure_collection",
            details={
                "purpose": "rag_chroma_collection_metadata",
                "conv_id": conv_id,
                "collection_name": collection_name,
            },
        ):
            await self.chroma.ensure_collection(
                conv_id=conv_id,
                collection_name=collection_name,
                embedding_model=embedding_model,
                effective_model=effective_model,
                timeout_sec=(
                    min(float(store_timeout_sec), 30.0) if store_timeout_sec > 0 else 30.0
                ),
            )
        await self.chroma.add_upsert_ids(
            conv_id=conv_id,
            collection_name=collection_name,
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=chroma_metadatas,
            batch_size=batch_size,
            timeout_sec=float(store_timeout_sec),
            cancel_wait_sec=float(cancel_wait_sec),
            token=token,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="mcp.storage.chunk_storage.store_chunks.chroma_add",
        )
        log_exception(
            logger,
            coerced,
            message="Failed to store chunks in ChromaDB collection.",
            operation=OPERATION,
            details={"conv_id": conv_id, "document_id": document_id},
        )
        raise


async def delete_chroma_vectors_under_lock(
    self: MCPStorageProtocol,
    conv_id: str,
    ids: Sequence[str],
) -> None:
    if not ids:
        return
    collection_name = await self.chroma.resolve_active_collection_name(conv_id)
    await self.chroma.delete(
        conv_id=conv_id,
        collection_name=collection_name,
        ids=list(ids),
        where=None,
        timeout_sec=30.0,
    )
