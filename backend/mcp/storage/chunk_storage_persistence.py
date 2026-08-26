"""SoAI - Chunk metadata persistence and rollback [backend/mcp/storage/chunk_storage_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.rag.job_operations import rag_job_lease_lost_details
from core.validation.coercion import coerce_non_negative_int_from_numberish

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.storage.internal_protocols import MCPStorageProtocol

__all__ = ("persist_chunks_and_collection_metadata",)


async def persist_chunks_and_collection_metadata(
    self: MCPStorageProtocol,
    *,
    conv_id: str,
    document_id: str,
    chunk_records: list[JSONDict],
    embedding_model: str,
    embedding_dimensions: int,
    effective_model: str,
    job_id: str | None = None,
    lease_token: str | None = None,
) -> None:
    if job_id and lease_token:
        chunks_persisted = await self.database_files.replace_rag_chunks_for_job(
            job_id=job_id,
            lease_token=lease_token,
            document_id=document_id,
            chunks=chunk_records,
        )
        if not chunks_persisted:
            raise StateError(
                "RAG job lease expired before chunk metadata persistence.",
                details=rag_job_lease_lost_details(),
            )
    else:
        await self.database_files.create_rag_chunks(chunk_records)
    collection_name = await self.chroma.resolve_active_collection_name(conv_id)
    collection_id = str(conv_id or "").strip()
    counts = await self.database_files.get_rag_counts_for_conversation(conv_id)
    document_count = (
        coerce_non_negative_int_from_numberish(counts.get("document_count", 0))
        if isinstance(counts, dict)
        else 0
    )
    chunk_count = (
        coerce_non_negative_int_from_numberish(counts.get("chunk_count", 0))
        if isinstance(counts, dict)
        else 0
    )
    chunk_count += len(chunk_records)
    await self.database_files.update_rag_collection_metadata(
        collection_id=collection_id,
        conv_id=conv_id,
        collection_name=collection_name,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
        document_count=document_count,
        chunk_count=chunk_count,
        metadata={"effective_model": effective_model},
    )
