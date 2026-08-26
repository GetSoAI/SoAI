"""SoAI - Core files database protocols [backend/core/files/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.database.requests import CreateRAGDocumentRequest
from core.files.database_types import (
    FileCatalogListPage,
    FileCatalogReconciliationRecord,
    FileCatalogRecord,
    FileCatalogRecordWithPath,
    RAGChunkRecord,
    RAGConversationChunkPreview,
    RAGDocumentRecord,
    RAGProcessingJobRecord,
)
from core.files.protocols_database_rag_config import DatabaseRAGConfigProtocol
from core.openai.file_list_limits import OPENAI_FILE_LIST_DEFAULT_LIMIT
from core.rag.job_operations import (
    RAGDocumentStatusJobUpdateRequest,
    RAGDocumentStatusUpdateRequest,
    RAGJobClaimOutcome,
    RAGJobCreateRequest,
    RAGJobFinalizeRequest,
    RAGJobLeaseRequest,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("DatabaseFilesProtocol",)


class DatabaseFilesProtocol(DatabaseRAGConfigProtocol, Protocol):

    async def get_active_linked_rag_documents(
        self,
        conv_id: str,
        user_id: int,
    ) -> list[dict[str, str | int]]: ...

    async def get_rag_documents_for_conversation(
        self,
        conv_id: str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[RAGDocumentRecord]: ...

    async def get_rag_documents_for_conversation_with_active_links(
        self,
        conv_id: str,
        user_id: int,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[RAGDocumentRecord]: ...

    async def get_rag_document_by_id(self, doc_id: str) -> RAGDocumentRecord | None: ...

    async def get_rag_processing_job(self, job_id: str) -> RAGProcessingJobRecord | None: ...

    async def list_claimable_rag_processing_jobs(
        self,
        *,
        now_ms: int,
        limit: int = 128,
    ) -> list[RAGProcessingJobRecord]: ...

    async def get_processing_rag_document_by_task_id(
        self,
        conv_id: str,
        task_id: str,
    ) -> RAGDocumentRecord | None: ...

    async def find_completed_rag_document_for_embedding_cache(
        self,
        conv_id: str,
        content_hash: str,
        *,
        chunking_strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: str,
    ) -> RAGDocumentRecord | None: ...

    async def find_recent_completed_rag_document_by_source_url_cache(
        self,
        conv_id: str,
        source_urls: list[str],
        created_at_min_ms: int,
        *,
        chunking_strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model: str,
    ) -> RAGDocumentRecord | None: ...

    async def create_rag_document(self, request: CreateRAGDocumentRequest) -> RAGDocumentRecord: ...

    async def create_rag_document_with_knowledge_item(
        self,
        request: CreateRAGDocumentRequest,
        *,
        knowledge_attachment_id: str,
        item_index: int,
        operation_type: str,
    ) -> tuple[RAGDocumentRecord, JSONDict]: ...

    async def update_rag_document_status(
        self,
        request: RAGDocumentStatusUpdateRequest,
    ) -> tuple[list[JSONDict], JSONDict | None]: ...

    async def update_rag_document_status_for_job(
        self,
        request: RAGDocumentStatusJobUpdateRequest,
    ) -> tuple[list[JSONDict], JSONDict | None]: ...

    async def delete_rag_document(
        self,
        doc_id: str,
        conv_id: str,
    ) -> tuple[bool, list[JSONDict]]: ...

    async def delete_rag_documents_for_conversation(
        self,
        conv_id: str,
    ) -> tuple[int, list[JSONDict]]: ...

    async def get_rag_chunks_for_conversation(
        self,
        conv_id: str,
    ) -> list[RAGConversationChunkPreview]: ...

    async def get_rag_chunks_for_conversation_page(
        self,
        conv_id: str,
        *,
        after_document_id: str | None = None,
        after_chunk_index: int | None = None,
        limit: int = 512,
    ) -> list[RAGConversationChunkPreview]: ...

    async def get_rag_chunks_for_document(self, document_id: str) -> list[RAGChunkRecord]: ...

    async def get_rag_chunks_for_document_cleanup(
        self,
        document_id: str,
    ) -> list[RAGChunkRecord]: ...

    async def get_rag_chunks_for_document_page(
        self,
        document_id: str,
        *,
        after_chunk_index: int | None = None,
        limit: int = 256,
    ) -> list[RAGChunkRecord]: ...

    async def get_rag_chunk_by_id(self, chunk_id: str) -> RAGChunkRecord | None: ...

    async def get_rag_chunks_by_ids_completed(
        self,
        chunk_ids: list[str],
    ) -> list[RAGChunkRecord]: ...

    async def create_rag_chunks(self, chunks: list[JSONDict]) -> None: ...

    async def replace_rag_chunks_for_job(
        self,
        *,
        job_id: str,
        lease_token: str,
        document_id: str,
        chunks: list[JSONDict],
    ) -> bool: ...

    async def create_rag_processing_job(self, request: RAGJobCreateRequest) -> bool: ...

    async def acquire_rag_job_lease(
        self,
        request: RAGJobLeaseRequest,
    ) -> RAGJobClaimOutcome: ...

    async def renew_rag_job_lease(
        self,
        job_id: str,
        lease_token: str,
        lease_expires_at_ms: int,
        now_ms: int,
    ) -> bool: ...

    async def release_rag_job_lease(
        self,
        job_id: str,
        lease_token: str,
        now_ms: int,
    ) -> None: ...

    async def finalize_rag_processing_job(self, request: RAGJobFinalizeRequest) -> bool: ...

    async def acquire_rag_maintenance_lock(
        self,
        *,
        conv_id: str,
        lock_type: str,
        owner_task_id: str,
        lease_token: str,
        lease_owner: str,
        lease_expires_at_ms: int,
        now_ms: int,
    ) -> bool: ...

    async def release_rag_maintenance_lock(
        self,
        *,
        conv_id: str,
        lease_token: str,
    ) -> None: ...

    async def renew_rag_maintenance_lock(
        self,
        *,
        conv_id: str,
        lease_token: str,
        lease_expires_at_ms: int,
        now_ms: int,
    ) -> bool: ...

    async def get_file_info_with_path(
        self,
        file_id: str,
        *,
        enforce_owner: bool = False,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> FileCatalogRecordWithPath | None: ...

    async def get_rag_counts_for_conversation(self, conv_id: str) -> dict[str, int]: ...

    async def get_rag_counts_for_conversation_with_active_links(
        self,
        conv_id: str,
        user_id: int,
    ) -> dict[str, int]: ...

    async def get_file_info(
        self,
        file_id: str,
        *,
        enforce_owner: bool = False,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> FileCatalogRecord | None: ...

    async def get_all_file_records_for_reconciliation(
        self,
    ) -> list[FileCatalogReconciliationRecord]: ...

    async def delete_files_by_ids(self, file_ids: list[str]) -> int: ...

    async def list_files(
        self,
        *,
        enforce_owner: bool = False,
        user_id: int | None = None,
        api_key_id: str | None = None,
        purpose: str | None = None,
        after: str | None = None,
        limit: int = OPENAI_FILE_LIST_DEFAULT_LIMIT,
        order: str = "desc",
    ) -> FileCatalogListPage: ...

    async def delete_file(
        self,
        file_id: str,
        *,
        enforce_owner: bool = False,
        user_id: int | None = None,
        api_key_id: str | None = None,
    ) -> bool: ...

    async def add_file(
        self,
        file_id: str,
        filename: str,
        purpose: str,
        size_bytes: int,
        content_sha256: str,
        created_at_ms: int,
        file_path: str,
        user_id: int | None,
        api_key_id: str | None,
        status: str,
        status_details: str | None,
    ) -> bool: ...
