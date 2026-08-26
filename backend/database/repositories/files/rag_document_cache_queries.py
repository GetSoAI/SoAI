"""SoAI - RAG document cache lookup queries [backend/database/repositories/files/rag_document_cache_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.files.database_types import RAGDocumentRecord
from core.validation.integers import is_strict_int
from database.core.query_execution import query_to_dicts
from database.repositories.files.record_parsing import parse_rag_document_record

__all__ = (
    "find_completed_rag_document_for_embedding_cache_query",
    "find_recent_completed_rag_document_by_source_url_query",
)


async def find_completed_rag_document_for_embedding_cache_query(
    database: aiosqlite.Connection,
    conv_id: str,
    content_hash: str,
    *,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> RAGDocumentRecord | None:
    rows = await query_to_dicts(
        database,
        """SELECT id, conv_id, user_id, file_id, filename, file_type, file_size_bytes,
           status, status_details, source_type, source_url, chunking_strategy, chunk_size,
           chunk_overlap, content_hash, total_chunks, processed_chunks, embedding_model,
           effective_embedding_model, embedding_dimensions,
           created_at_ms, processing_started_at_ms, processing_completed_at_ms, error_message, metadata
           FROM rag_documents
           WHERE conv_id = ?
             AND status = 'completed'
             AND content_hash = ?
             AND chunking_strategy = ?
             AND chunk_size = ?
             AND chunk_overlap = ?
             AND embedding_model = ?
           ORDER BY created_at_ms DESC
           LIMIT 1""",
        (
            conv_id,
            content_hash,
            chunking_strategy,
            chunk_size,
            chunk_overlap,
            embedding_model,
        ),
    )
    if not rows:
        return None
    return parse_rag_document_record(rows[0])


async def find_recent_completed_rag_document_by_source_url_query(
    database: aiosqlite.Connection,
    conv_id: str,
    source_urls: list[str],
    created_at_min_ms: int,
    *,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> RAGDocumentRecord | None:
    if not source_urls:
        return None
    effective_created_at_min_ms = int(created_at_min_ms) if is_strict_int(created_at_min_ms) else 0
    placeholders = ", ".join("?" for _ in source_urls)
    rows = await query_to_dicts(
        database,
        f"""SELECT id, conv_id, user_id, file_id, filename, file_type, file_size_bytes,
           status, status_details, source_type, source_url, chunking_strategy, chunk_size,
           chunk_overlap, content_hash, total_chunks, processed_chunks, embedding_model,
           effective_embedding_model, embedding_dimensions,
           created_at_ms, processing_started_at_ms, processing_completed_at_ms, error_message, metadata
           FROM rag_documents
           WHERE conv_id = ?
             AND status = 'completed'
             AND created_at_ms >= ?
             AND source_url IN ({placeholders})
             AND chunking_strategy = ?
             AND chunk_size = ?
             AND chunk_overlap = ?
             AND embedding_model = ?
           ORDER BY created_at_ms DESC
           LIMIT 1""",
        (
            conv_id,
            effective_created_at_min_ms,
            *source_urls,
            chunking_strategy,
            chunk_size,
            chunk_overlap,
            embedding_model,
        ),
    )
    if not rows:
        return None
    return parse_rag_document_record(rows[0])
