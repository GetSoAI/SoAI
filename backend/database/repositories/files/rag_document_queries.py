"""SoAI - Conversation RAG document queries [backend/database/repositories/files/rag_document_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.files.database_types import RAGDocumentRecord
from core.validation.integers import is_strict_int
from database.core.query_execution import query_to_dicts
from database.repositories.files.record_parsing import parse_rag_document_record

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "get_processing_rag_document_by_task_id_query",
    "get_rag_document_by_id_query",
    "get_rag_documents_for_conversation_query",
)


async def get_rag_documents_for_conversation_query(
    database: aiosqlite.Connection,
    conv_id: str,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[RAGDocumentRecord]:
    if not is_strict_int(offset):
        raise StateError("RAG documents offset must be an integer.")
    if offset < 0:
        raise StateError("RAG documents offset must be non-negative.")
    if limit is not None:
        if not is_strict_int(limit):
            raise StateError("RAG documents limit must be an integer.")
        if limit < 0:
            raise StateError("RAG documents limit must be non-negative.")
    sql = """SELECT id, conv_id, user_id, file_id, filename, file_type, file_size_bytes,
           status, status_details, source_type, source_url, chunking_strategy, chunk_size,
           chunk_overlap, content_hash, total_chunks, processed_chunks, embedding_model,
           effective_embedding_model, embedding_dimensions,
           created_at_ms, processing_started_at_ms, processing_completed_at_ms, error_message, metadata
           FROM rag_documents WHERE conv_id = ? ORDER BY created_at_ms DESC"""
    params: list[SQLiteValue] = [conv_id]
    if limit is not None:
        params.append(limit)
        params.append(offset)
        sql = f"{sql} LIMIT ? OFFSET ?"
    rows = await query_to_dicts(database, sql, tuple(params))
    return [parse_rag_document_record(row) for row in rows]


async def get_rag_document_by_id_query(
    database: aiosqlite.Connection,
    doc_id: str,
) -> RAGDocumentRecord | None:
    rows = await query_to_dicts(
        database,
        """SELECT id, conv_id, user_id, file_id, filename, file_type, file_size_bytes,
           status, status_details, source_type, source_url, chunking_strategy, chunk_size,
           chunk_overlap, content_hash, total_chunks, processed_chunks, embedding_model,
           effective_embedding_model, embedding_dimensions,
           created_at_ms, processing_started_at_ms, processing_completed_at_ms, error_message, metadata
           FROM rag_documents WHERE id = ?""",
        (doc_id,),
    )
    if not rows:
        return None
    return parse_rag_document_record(rows[0])


async def get_processing_rag_document_by_task_id_query(
    database: aiosqlite.Connection,
    conv_id: str,
    task_id: str,
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
             AND status IN ('queued', 'fetching', 'parsing', 'chunking', 'embedding')
             AND json_extract(metadata, '$.task_id') = ?
           ORDER BY created_at_ms DESC
           LIMIT 1""",
        (conv_id, task_id),
    )
    if not rows:
        return None
    return parse_rag_document_record(rows[0])
