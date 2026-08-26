"""SoAI - RAG document read methods for DatabaseFiles [backend/database/repositories/files/service_rag_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.files.database_types import (
    RAGChunkRecord,
    RAGConversationChunkPreview,
    RAGConversationConfigRecord,
    RAGDocumentRecord,
    RAGProcessingJobRecord,
    RAGVectorCollectionMetadataRecord,
)
from database.repositories.files.internal_protocols import DatabaseFilesRagProtocol
from database.repositories.files.rag_chunks import (
    get_rag_chunk_by_id_query,
    get_rag_chunks_by_ids_completed_query,
    get_rag_chunks_for_conversation_page_query,
    get_rag_chunks_for_conversation_query,
    get_rag_chunks_for_document_cleanup_query,
    get_rag_chunks_for_document_page_query,
    get_rag_chunks_for_document_query,
    get_rag_counts_for_conversation_query,
)
from database.repositories.files.rag_config import (
    get_rag_collection_metadata_query,
    get_rag_config_query,
)
from database.repositories.files.rag_document_cache_queries import (
    find_completed_rag_document_for_embedding_cache_query,
    find_recent_completed_rag_document_by_source_url_query,
)
from database.repositories.files.rag_document_queries import (
    get_processing_rag_document_by_task_id_query,
    get_rag_document_by_id_query,
    get_rag_documents_for_conversation_query,
)
from database.repositories.files.rag_job_reads import (
    get_rag_processing_job_query,
    list_claimable_rag_processing_jobs_query,
)
from database.repositories.files.rag_linked_documents import (
    get_active_linked_rag_documents_query,
    get_rag_counts_for_conversation_with_active_links_query,
    get_rag_documents_for_conversation_with_active_links_query,
)

__all__ = (
    "find_completed_rag_document_for_embedding_cache",
    "find_recent_completed_rag_document_by_source_url_cache",
    "get_active_linked_rag_documents",
    "get_processing_rag_document_by_task_id",
    "get_rag_chunk_by_id",
    "get_rag_chunks_by_ids_completed",
    "get_rag_chunks_for_conversation",
    "get_rag_chunks_for_conversation_page",
    "get_rag_chunks_for_document",
    "get_rag_chunks_for_document_cleanup",
    "get_rag_chunks_for_document_page",
    "get_rag_collection_metadata",
    "get_rag_config",
    "get_rag_counts_for_conversation",
    "get_rag_counts_for_conversation_with_active_links",
    "get_rag_document_by_id",
    "get_rag_documents_for_conversation",
    "get_rag_documents_for_conversation_with_active_links",
    "get_rag_processing_job",
    "list_claimable_rag_processing_jobs",
)


async def get_rag_documents_for_conversation(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[RAGDocumentRecord]:
    return await self.core.reader.execute_read(
        get_rag_documents_for_conversation_query,
        conv_id,
        offset=offset,
        limit=limit,
    )


async def get_rag_documents_for_conversation_with_active_links(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    user_id: int,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[RAGDocumentRecord]:
    return await self.core.reader.execute_read(
        get_rag_documents_for_conversation_with_active_links_query,
        conv_id,
        user_id,
        offset=offset,
        limit=limit,
    )


async def get_rag_processing_job(
    self: DatabaseFilesRagProtocol,
    job_id: str,
) -> RAGProcessingJobRecord | None:
    return await self.core.reader.execute_read(get_rag_processing_job_query, job_id)


async def list_claimable_rag_processing_jobs(
    self: DatabaseFilesRagProtocol,
    *,
    now_ms: int,
    limit: int = 128,
) -> list[RAGProcessingJobRecord]:
    return await self.core.reader.execute_read(
        list_claimable_rag_processing_jobs_query,
        now_ms=now_ms,
        limit=limit,
    )


async def get_rag_document_by_id(
    self: DatabaseFilesRagProtocol,
    doc_id: str,
) -> RAGDocumentRecord | None:
    return await self.core.reader.execute_read(get_rag_document_by_id_query, doc_id)


async def get_processing_rag_document_by_task_id(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    task_id: str,
) -> RAGDocumentRecord | None:
    return await self.core.reader.execute_read(
        get_processing_rag_document_by_task_id_query,
        conv_id,
        task_id,
    )


async def find_completed_rag_document_for_embedding_cache(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    content_hash: str,
    *,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> RAGDocumentRecord | None:
    return await self.core.reader.execute_read(
        find_completed_rag_document_for_embedding_cache_query,
        conv_id,
        content_hash,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
    )


async def find_recent_completed_rag_document_by_source_url_cache(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    source_urls: list[str],
    created_at_min_ms: int,
    *,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> RAGDocumentRecord | None:
    return await self.core.reader.execute_read(
        find_recent_completed_rag_document_by_source_url_query,
        conv_id,
        source_urls,
        created_at_min_ms,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_model=embedding_model,
    )


async def get_rag_chunks_for_document(
    self: DatabaseFilesRagProtocol,
    document_id: str,
) -> list[RAGChunkRecord]:
    return await self.core.reader.execute_read(get_rag_chunks_for_document_query, document_id)


async def get_rag_chunks_for_document_cleanup(
    self: DatabaseFilesRagProtocol,
    document_id: str,
) -> list[RAGChunkRecord]:
    return await self.core.reader.execute_read(
        get_rag_chunks_for_document_cleanup_query,
        document_id,
    )


async def get_rag_chunks_for_document_page(
    self: DatabaseFilesRagProtocol,
    document_id: str,
    *,
    after_chunk_index: int | None = None,
    limit: int = 256,
) -> list[RAGChunkRecord]:
    return await self.core.reader.execute_read(
        get_rag_chunks_for_document_page_query,
        document_id,
        after_chunk_index=after_chunk_index,
        limit=limit,
    )


async def get_rag_chunk_by_id(
    self: DatabaseFilesRagProtocol,
    chunk_id: str,
) -> RAGChunkRecord | None:
    return await self.core.reader.execute_read(get_rag_chunk_by_id_query, chunk_id)


async def get_rag_chunks_by_ids_completed(
    self: DatabaseFilesRagProtocol,
    chunk_ids: list[str],
) -> list[RAGChunkRecord]:
    return await self.core.reader.execute_read(get_rag_chunks_by_ids_completed_query, chunk_ids)


async def get_rag_chunks_for_conversation(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
) -> list[RAGConversationChunkPreview]:
    return await self.core.reader.execute_read(get_rag_chunks_for_conversation_query, conv_id)


async def get_rag_chunks_for_conversation_page(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    *,
    after_document_id: str | None = None,
    after_chunk_index: int | None = None,
    limit: int = 512,
) -> list[RAGConversationChunkPreview]:
    return await self.core.reader.execute_read(
        get_rag_chunks_for_conversation_page_query,
        conv_id,
        after_document_id=after_document_id,
        after_chunk_index=after_chunk_index,
        limit=limit,
    )


async def get_rag_counts_for_conversation(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
) -> dict[str, int]:
    return await self.core.reader.execute_read(get_rag_counts_for_conversation_query, conv_id)


async def get_rag_counts_for_conversation_with_active_links(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    user_id: int,
) -> dict[str, int]:
    return await self.core.reader.execute_read(
        get_rag_counts_for_conversation_with_active_links_query,
        conv_id,
        user_id,
    )


async def get_rag_config(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
) -> RAGConversationConfigRecord | None:
    return await self.core.reader.execute_read(get_rag_config_query, conv_id)


async def get_rag_collection_metadata(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
) -> RAGVectorCollectionMetadataRecord | None:
    return await self.core.reader.execute_read(get_rag_collection_metadata_query, conv_id)


async def get_active_linked_rag_documents(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
    user_id: int,
) -> list[dict[str, str | int]]:
    return await self.core.reader.execute_read(
        get_active_linked_rag_documents_query,
        conv_id,
        user_id,
    )
