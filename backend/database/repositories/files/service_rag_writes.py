"""SoAI - RAG document write methods for DatabaseFiles [backend/database/repositories/files/service_rag_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.requests import (
    CreateRAGDocumentRequest,
    UpdateRAGConfigRequest,
    UpdateRAGConfigWithDefaultsRequest,
)
from core.errors.exceptions import ValidationError
from core.files.database_types import RAGConfigWithDefaultsResult, RAGDocumentRecord
from core.rag.job_operations import RAGDocumentStatusUpdateRequest
from core.types.json import JSONDict
from database.repositories.files.internal_protocols import DatabaseFilesRagProtocol
from database.repositories.files.rag_chunks import sync_create_rag_chunks
from database.repositories.files.rag_config import (
    sync_activate_rag_collection,
    sync_delete_rag_collection_metadata_for_conversation,
    sync_update_rag_collection_metadata,
    sync_update_rag_config,
)
from database.repositories.files.rag_config_defaults import sync_update_rag_config_with_defaults
from database.repositories.files.rag_document_mutations import (
    sync_delete_rag_document,
    sync_delete_rag_documents_for_conversation,
)
from database.repositories.files.rag_document_status_updates import (
    sync_update_rag_document_status,
)
from database.repositories.files.rag_documents import (
    sync_create_rag_document,
    sync_create_rag_document_with_knowledge_item,
)

__all__ = (
    "activate_rag_collection",
    "create_rag_chunks",
    "create_rag_document",
    "create_rag_document_with_knowledge_item",
    "delete_rag_collection_metadata_for_conversation",
    "delete_rag_document",
    "delete_rag_documents_for_conversation",
    "update_rag_collection_metadata",
    "update_rag_config",
    "update_rag_config_with_defaults",
    "update_rag_document_status",
)


async def create_rag_document(
    self: DatabaseFilesRagProtocol,
    request: CreateRAGDocumentRequest,
) -> RAGDocumentRecord:
    filename = str(request.filename or "").strip()
    if not filename:
        raise ValidationError(
            "RAG document filename must be a non-empty string.",
            operation="database.files.create_rag_document",
        )
    return await self.core.writer.queue_write_operation(
        sync_create_rag_document,
        request.doc_id,
        request.conv_id,
        request.user_id,
        request.file_id,
        filename,
        request.file_type,
        request.file_size_bytes,
        request.status,
        request.source_type,
        request.source_url,
        request.chunking_strategy,
        request.chunk_size,
        request.chunk_overlap,
        request.embedding_model,
        request.metadata,
    )


async def create_rag_document_with_knowledge_item(
    self: DatabaseFilesRagProtocol,
    request: CreateRAGDocumentRequest,
    *,
    knowledge_attachment_id: str,
    item_index: int,
    operation_type: str,
) -> tuple[RAGDocumentRecord, JSONDict]:
    filename = str(request.filename or "").strip()
    if not filename:
        raise ValidationError(
            "RAG document filename must be a non-empty string.",
            operation="database.files.create_rag_document_with_knowledge_item",
        )
    return await self.core.writer.queue_write_operation(
        sync_create_rag_document_with_knowledge_item,
        request.doc_id,
        request.conv_id,
        request.user_id,
        request.file_id,
        filename,
        request.file_type,
        request.file_size_bytes,
        request.status,
        request.source_type,
        request.source_url,
        request.chunking_strategy,
        request.chunk_size,
        request.chunk_overlap,
        request.embedding_model,
        request.metadata,
        knowledge_attachment_id,
        item_index,
        operation_type,
    )


async def update_rag_document_status(
    self: DatabaseFilesRagProtocol,
    request: RAGDocumentStatusUpdateRequest,
) -> tuple[list[JSONDict], JSONDict | None]:
    return await self.core.writer.queue_write_operation(
        sync_update_rag_document_status,
        request,
    )


async def delete_rag_document(
    self: DatabaseFilesRagProtocol,
    doc_id: str,
    conv_id: str,
) -> tuple[bool, list[JSONDict]]:
    return await self.core.writer.queue_write_operation(
        sync_delete_rag_document,
        doc_id,
        conv_id,
    )


async def delete_rag_documents_for_conversation(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
) -> tuple[int, list[JSONDict]]:
    return await self.core.writer.queue_write_operation(
        sync_delete_rag_documents_for_conversation,
        conv_id,
    )


async def create_rag_chunks(self: DatabaseFilesRagProtocol, chunks: list[JSONDict]) -> None:
    await self.core.writer.queue_write_operation(
        sync_create_rag_chunks,
        chunks,
    )


async def update_rag_config(
    self: DatabaseFilesRagProtocol,
    request: UpdateRAGConfigRequest,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_update_rag_config,
        request.conv_id,
        request.enabled,
        request.retrieval_strategy,
        request.top_k,
        request.similarity_threshold,
        request.chunking_strategy,
        request.chunk_size,
        request.chunk_overlap,
        request.embedding_model,
        request.config_metadata,
    )


async def update_rag_config_with_defaults(
    self: DatabaseFilesRagProtocol,
    request: UpdateRAGConfigWithDefaultsRequest,
) -> RAGConfigWithDefaultsResult:
    return await self.core.writer.queue_write_operation(
        sync_update_rag_config_with_defaults,
        request,
    )


async def update_rag_collection_metadata(
    self: DatabaseFilesRagProtocol,
    collection_id: str,
    conv_id: str,
    collection_name: str,
    embedding_model: str,
    embedding_dimensions: int,
    document_count: int,
    chunk_count: int,
    metadata: JSONDict | None = None,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_update_rag_collection_metadata,
        collection_id,
        conv_id,
        collection_name,
        embedding_model,
        embedding_dimensions,
        document_count,
        chunk_count,
        metadata,
    )


async def activate_rag_collection(
    self: DatabaseFilesRagProtocol,
    collection_id: str,
    conv_id: str,
    collection_name: str,
    embedding_model: str,
    embedding_dimensions: int,
    document_count: int,
    chunk_count: int,
    metadata: JSONDict | None = None,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_activate_rag_collection,
        collection_id,
        conv_id,
        collection_name,
        embedding_model,
        embedding_dimensions,
        document_count,
        chunk_count,
        metadata,
    )


async def delete_rag_collection_metadata_for_conversation(
    self: DatabaseFilesRagProtocol,
    conv_id: str,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_delete_rag_collection_metadata_for_conversation,
        conv_id,
    )
