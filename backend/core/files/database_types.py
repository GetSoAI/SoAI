"""SoAI - Database record shapes for files and RAG [backend/core/files/database_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NotRequired, Required, TypedDict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "FileCatalogListPage",
    "FileCatalogReconciliationRecord",
    "FileCatalogRecord",
    "FileCatalogRecordWithPath",
    "RAGChunkRecord",
    "RAGConversationChunkPreview",
    "RAGConversationConfigRecord",
    "RAGConfigWithDefaultsResult",
    "RAGDocumentRecord",
    "RAGProcessingJobRecord",
    "RAGVectorCollectionMetadataRecord",
)


class FileCatalogRecord(TypedDict):
    id: Required[str]
    filename: Required[str]
    purpose: Required[str]
    size_bytes: Required[int]
    content_sha256: Required[str]
    created_at_ms: Required[int]
    user_id: Required[int | None]
    api_key_id: Required[str | None]
    status: Required[str]
    status_details: NotRequired[str | None]


class FileCatalogRecordWithPath(FileCatalogRecord):
    file_path: Required[str]


class FileCatalogReconciliationRecord(TypedDict):
    id: Required[str]
    file_path: Required[str]


@dataclass(frozen=True, slots=True)
class FileCatalogListPage:
    records: list[FileCatalogRecord]
    has_more: bool
    invalid_after: bool = False


class RAGConversationConfigRecord(TypedDict):
    conv_id: Required[str]
    enabled: Required[bool]
    retrieval_strategy: Required[str]
    top_k: Required[int]
    similarity_threshold: Required[float]
    chunking_strategy: Required[str]
    chunk_size: Required[int]
    chunk_overlap: Required[int]
    embedding_model: Required[str | None]
    config_metadata: Required[JSONValue | None]
    created_at_ms: Required[int]
    last_modified_at_ms: Required[int]


@dataclass(frozen=True, slots=True)
class RAGConfigWithDefaultsResult:
    config: RAGConversationConfigRecord
    superseded: bool
    preferences: JSONDict | None = None


class RAGVectorCollectionMetadataRecord(TypedDict):
    id: Required[str]
    conv_id: Required[str]
    collection_name: Required[str]
    embedding_model: Required[str]
    embedding_dimensions: Required[int]
    document_count: Required[int]
    chunk_count: Required[int]
    created_at_ms: Required[int]
    last_synced_at_ms: Required[int]
    metadata: Required[JSONValue | None]


class RAGDocumentRecord(TypedDict):
    id: Required[str]
    conv_id: Required[str]
    user_id: Required[int]
    file_id: Required[str | None]
    filename: Required[str]
    file_type: Required[str]
    file_size_bytes: Required[int]
    status: Required[str]
    status_details: Required[str | None]
    source_type: Required[str]
    source_url: Required[str | None]
    chunking_strategy: Required[str]
    chunk_size: Required[int]
    chunk_overlap: Required[int]
    content_hash: Required[str | None]
    total_chunks: Required[int | None]
    processed_chunks: Required[int | None]
    embedding_model: Required[str | None]
    effective_embedding_model: Required[str | None]
    embedding_dimensions: Required[int | None]
    created_at_ms: Required[int]
    processing_started_at_ms: Required[int | None]
    processing_completed_at_ms: Required[int | None]
    error_message: Required[str | None]
    metadata: Required[JSONValue | None]


class RAGChunkRecord(TypedDict):
    id: Required[str]
    document_id: Required[str]
    chunk_index: Required[int]
    content: Required[str]
    content_hash: Required[str]
    token_count: Required[int | None]
    start_char: Required[int | None]
    end_char: Required[int | None]
    metadata: Required[JSONValue | None]
    created_at_ms: Required[int]


class RAGConversationChunkPreview(TypedDict):
    id: Required[str]
    document_id: Required[str]
    chunk_index: Required[int]
    content: Required[str]
    token_count: Required[int | None]
    start_char: Required[int | None]
    end_char: Required[int | None]


class RAGProcessingJobRecord(TypedDict):
    job_id: Required[str]
    job_type: Required[str]
    conv_id: Required[str]
    user_id: Required[int]
    document_id: Required[str | None]
    task_id: Required[str]
    status: Required[str]
    payload: Required[JSONValue]
    spool_path: Required[str | None]
    lease_token: Required[str | None]
    lease_owner: Required[str | None]
    lease_expires_at_ms: Required[int | None]
    attempt_count: Required[int]
    last_error: Required[str | None]
    created_at_ms: Required[int]
    updated_at_ms: Required[int]
    completed_at_ms: Required[int | None]
