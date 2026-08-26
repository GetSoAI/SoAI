"""SoAI - Typed record parsing helpers for files and RAG repositories [backend/database/repositories/files/record_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.database_types import (
    FileCatalogReconciliationRecord,
    FileCatalogRecord,
    FileCatalogRecordWithPath,
    RAGChunkRecord,
    RAGConversationChunkPreview,
    RAGConversationConfigRecord,
    RAGDocumentRecord,
    RAGVectorCollectionMetadataRecord,
)
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from database.core.json_codec import coerce_optional_json_from_sqlite_row
from database.core.sqlite_numbers import (
    coerce_optional_int_from_sqlite_row,
    coerce_optional_str_from_sqlite_row,
    coerce_required_bool_from_sqlite_row,
    coerce_required_float_from_sqlite_row,
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "parse_file_catalog_reconciliation_record",
    "parse_file_catalog_record",
    "parse_file_catalog_record_with_path",
    "parse_rag_chunk_record",
    "parse_rag_conversation_chunk_preview",
    "parse_rag_conversation_config_record",
    "parse_rag_document_record",
    "parse_rag_vector_collection_metadata_record",
)


def parse_file_catalog_record(row: SQLiteRow) -> FileCatalogRecord:
    status_details = coerce_optional_str_from_sqlite_row(row, "status_details")
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
        "filename": coerce_required_nonempty_str_from_sqlite_row(row, "filename"),
        "purpose": coerce_required_nonempty_str_from_sqlite_row(row, "purpose"),
        "size_bytes": coerce_required_int_from_sqlite_row(row, "size_bytes"),
        "content_sha256": require_canonical_sha256_hexdigest(
            coerce_required_nonempty_str_from_sqlite_row(row, "content_sha256"),
            label="File catalog content_sha256",
        ),
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        "user_id": coerce_optional_int_from_sqlite_row(row, "user_id"),
        "api_key_id": coerce_optional_str_from_sqlite_row(row, "api_key_id"),
        "status": coerce_required_nonempty_str_from_sqlite_row(row, "status"),
        "status_details": status_details,
    }


def parse_file_catalog_record_with_path(row: SQLiteRow) -> FileCatalogRecordWithPath:
    base = parse_file_catalog_record(row)
    file_path = coerce_required_nonempty_str_from_sqlite_row(row, "file_path")
    return {**base, "file_path": file_path}


def parse_file_catalog_reconciliation_record(row: SQLiteRow) -> FileCatalogReconciliationRecord:
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
        "file_path": coerce_required_nonempty_str_from_sqlite_row(row, "file_path"),
    }


def parse_rag_conversation_config_record(row: SQLiteRow) -> RAGConversationConfigRecord:
    return {
        "conv_id": coerce_required_nonempty_str_from_sqlite_row(row, "conv_id"),
        "enabled": coerce_required_bool_from_sqlite_row(row, "enabled"),
        "retrieval_strategy": coerce_required_nonempty_str_from_sqlite_row(
            row,
            "retrieval_strategy",
        ),
        "top_k": coerce_required_int_from_sqlite_row(row, "top_k"),
        "similarity_threshold": coerce_required_float_from_sqlite_row(row, "similarity_threshold"),
        "chunking_strategy": coerce_required_nonempty_str_from_sqlite_row(row, "chunking_strategy"),
        "chunk_size": coerce_required_int_from_sqlite_row(row, "chunk_size"),
        "chunk_overlap": coerce_required_int_from_sqlite_row(row, "chunk_overlap"),
        "embedding_model": coerce_optional_str_from_sqlite_row(row, "embedding_model"),
        "config_metadata": coerce_optional_json_from_sqlite_row(row, "config_metadata"),
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        "last_modified_at_ms": coerce_required_int_from_sqlite_row(row, "last_modified_at_ms"),
    }


def parse_rag_vector_collection_metadata_record(
    row: SQLiteRow,
) -> RAGVectorCollectionMetadataRecord:
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
        "conv_id": coerce_required_nonempty_str_from_sqlite_row(row, "conv_id"),
        "collection_name": coerce_required_nonempty_str_from_sqlite_row(row, "collection_name"),
        "embedding_model": coerce_required_nonempty_str_from_sqlite_row(row, "embedding_model"),
        "embedding_dimensions": coerce_required_int_from_sqlite_row(row, "embedding_dimensions"),
        "document_count": coerce_required_int_from_sqlite_row(row, "document_count"),
        "chunk_count": coerce_required_int_from_sqlite_row(row, "chunk_count"),
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        "last_synced_at_ms": coerce_required_int_from_sqlite_row(row, "last_synced_at_ms"),
        "metadata": coerce_optional_json_from_sqlite_row(row, "metadata"),
    }


def parse_rag_document_record(row: SQLiteRow) -> RAGDocumentRecord:
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
        "conv_id": coerce_required_nonempty_str_from_sqlite_row(row, "conv_id"),
        "user_id": coerce_required_int_from_sqlite_row(row, "user_id"),
        "file_id": coerce_optional_str_from_sqlite_row(row, "file_id"),
        "filename": coerce_required_nonempty_str_from_sqlite_row(row, "filename"),
        "file_type": coerce_required_nonempty_str_from_sqlite_row(row, "file_type"),
        "file_size_bytes": coerce_required_int_from_sqlite_row(row, "file_size_bytes"),
        "status": coerce_required_nonempty_str_from_sqlite_row(row, "status"),
        "status_details": coerce_optional_str_from_sqlite_row(row, "status_details"),
        "source_type": coerce_required_nonempty_str_from_sqlite_row(row, "source_type"),
        "source_url": coerce_optional_str_from_sqlite_row(row, "source_url"),
        "chunking_strategy": coerce_required_nonempty_str_from_sqlite_row(row, "chunking_strategy"),
        "chunk_size": coerce_required_int_from_sqlite_row(row, "chunk_size"),
        "chunk_overlap": coerce_required_int_from_sqlite_row(row, "chunk_overlap"),
        "content_hash": coerce_optional_str_from_sqlite_row(row, "content_hash"),
        "total_chunks": coerce_optional_int_from_sqlite_row(row, "total_chunks"),
        "processed_chunks": coerce_optional_int_from_sqlite_row(row, "processed_chunks"),
        "embedding_model": coerce_optional_str_from_sqlite_row(row, "embedding_model"),
        "effective_embedding_model": coerce_optional_str_from_sqlite_row(
            row,
            "effective_embedding_model",
        ),
        "embedding_dimensions": coerce_optional_int_from_sqlite_row(row, "embedding_dimensions"),
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        "processing_started_at_ms": coerce_optional_int_from_sqlite_row(
            row,
            "processing_started_at_ms",
        ),
        "processing_completed_at_ms": coerce_optional_int_from_sqlite_row(
            row,
            "processing_completed_at_ms",
        ),
        "error_message": coerce_optional_str_from_sqlite_row(row, "error_message"),
        "metadata": coerce_optional_json_from_sqlite_row(row, "metadata"),
    }


def parse_rag_chunk_record(row: SQLiteRow) -> RAGChunkRecord:
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
        "document_id": coerce_required_nonempty_str_from_sqlite_row(row, "document_id"),
        "chunk_index": coerce_required_int_from_sqlite_row(row, "chunk_index"),
        "content": coerce_required_nonempty_str_from_sqlite_row(row, "content"),
        "content_hash": coerce_required_nonempty_str_from_sqlite_row(row, "content_hash"),
        "token_count": coerce_optional_int_from_sqlite_row(row, "token_count"),
        "start_char": coerce_optional_int_from_sqlite_row(row, "start_char"),
        "end_char": coerce_optional_int_from_sqlite_row(row, "end_char"),
        "metadata": coerce_optional_json_from_sqlite_row(row, "metadata"),
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
    }


def parse_rag_conversation_chunk_preview(row: SQLiteRow) -> RAGConversationChunkPreview:
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "id"),
        "document_id": coerce_required_nonempty_str_from_sqlite_row(row, "document_id"),
        "chunk_index": coerce_required_int_from_sqlite_row(row, "chunk_index"),
        "content": coerce_required_nonempty_str_from_sqlite_row(row, "content"),
        "token_count": coerce_optional_int_from_sqlite_row(row, "token_count"),
        "start_char": coerce_optional_int_from_sqlite_row(row, "start_char"),
        "end_char": coerce_optional_int_from_sqlite_row(row, "end_char"),
    }
