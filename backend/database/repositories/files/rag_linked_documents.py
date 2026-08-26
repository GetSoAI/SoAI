"""SoAI - RAG linked document read queries [backend/database/repositories/files/rag_linked_documents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from core.files.database_types import RAGDocumentRecord
from core.validation.integers import is_strict_int
from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite_numberish
from database.repositories.files.record_parsing import parse_rag_document_record

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow, SQLiteValue

__all__ = (
    "get_active_linked_rag_documents_query",
    "get_rag_counts_for_conversation_with_active_links_query",
    "get_rag_documents_for_conversation_with_active_links_query",
)


def _validate_page_args(offset: int, limit: int | None) -> None:
    if not is_strict_int(offset):
        raise StateError("Linked RAG documents offset must be an integer.")
    if offset < 0:
        raise StateError("Linked RAG documents offset must be non-negative.")
    if limit is not None:
        if not is_strict_int(limit):
            raise StateError("Linked RAG documents limit must be an integer.")
        if limit < 0:
            raise StateError("Linked RAG documents limit must be non-negative.")


def _active_linked_documents_filter() -> str:
    return """
        FROM rag_linked_documents link
        JOIN webui_conversation_knowledge_attachments summary
          ON summary.id = link.target_knowledge_attachment_id
         AND summary.conv_id = link.target_conv_id
         AND summary.user_id = link.target_user_id
        JOIN rag_documents document
          ON document.id = link.source_document_id
         AND document.conv_id = link.source_conv_id
         AND document.user_id = link.source_user_id
        WHERE link.target_conv_id = ?
          AND link.target_user_id = ?
          AND link.status = 'active'
          AND summary.state = 'committed'
          AND summary.source_type = 'linked_knowledge'
          AND document.status = 'completed'
          AND document.conv_id != link.target_conv_id
        """


def _visible_documents_filter() -> str:
    return f"""
        SELECT document.id AS document_id
        FROM rag_documents document
        WHERE document.conv_id = ?
        UNION
        SELECT linked.document_id
        FROM (
            SELECT DISTINCT document.id AS document_id
            {_active_linked_documents_filter()}
        ) linked
        """


async def get_rag_documents_for_conversation_with_active_links_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    *,
    offset: int = 0,
    limit: int | None = None,
) -> list[RAGDocumentRecord]:
    _validate_page_args(offset, limit)
    sql = f"""
        WITH visible_documents AS (
            {_visible_documents_filter()}
        )
        SELECT
            document.id, document.conv_id, document.user_id, document.file_id,
            document.filename, document.file_type, document.file_size_bytes,
            document.status, document.status_details, document.source_type,
            document.source_url, document.chunking_strategy, document.chunk_size,
            document.chunk_overlap, document.content_hash, document.total_chunks,
            document.processed_chunks, document.embedding_model,
            document.effective_embedding_model, document.embedding_dimensions,
            document.created_at_ms, document.processing_started_at_ms,
            document.processing_completed_at_ms, document.error_message, document.metadata
        FROM rag_documents document
        JOIN visible_documents visible
          ON visible.document_id = document.id
        ORDER BY document.created_at_ms DESC, document.id ASC
        """
    params: list[SQLiteValue] = [conv_id, conv_id, user_id]
    if limit is not None:
        params.append(limit)
        params.append(offset)
        sql = f"{sql} LIMIT ? OFFSET ?"
    rows = await query_to_dicts(database, sql, tuple(params))
    return [parse_rag_document_record(row) for row in rows]


async def get_rag_counts_for_conversation_with_active_links_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
) -> dict[str, int]:
    rows = await query_to_dicts(
        database,
        f"""
        WITH visible_documents AS (
            {_visible_documents_filter()}
        )
        SELECT
             COUNT(*) AS document_count,
             SUM(CASE WHEN document.status = 'queued' THEN 1 ELSE 0 END) AS queued,
             SUM(CASE WHEN document.status = 'fetching' THEN 1 ELSE 0 END) AS fetching,
             SUM(CASE WHEN document.status = 'parsing' THEN 1 ELSE 0 END) AS parsing,
             SUM(CASE WHEN document.status = 'chunking' THEN 1 ELSE 0 END) AS chunking,
             SUM(CASE WHEN document.status = 'embedding' THEN 1 ELSE 0 END) AS embedding,
             SUM(CASE WHEN document.status = 'completed' THEN 1 ELSE 0 END) AS completed,
             SUM(CASE WHEN document.status = 'error' THEN 1 ELSE 0 END) AS error,
             (SELECT COUNT(*)
              FROM rag_chunks chunk
              JOIN visible_documents visible_chunk
                ON visible_chunk.document_id = chunk.document_id) AS chunk_count
        FROM rag_documents document
        JOIN visible_documents visible
          ON visible.document_id = document.id
        """,
        (conv_id, conv_id, user_id),
    )
    if not rows:
        return _empty_counts()
    return _parse_counts(rows[0])


def _empty_counts() -> dict[str, int]:
    return {
        "document_count": 0,
        "chunk_count": 0,
        "queued": 0,
        "fetching": 0,
        "parsing": 0,
        "chunking": 0,
        "embedding": 0,
        "completed": 0,
        "error": 0,
    }


def _parse_counts(row: SQLiteRow) -> dict[str, int]:
    return {
        "document_count": coerce_non_negative_int_from_sqlite_numberish(row.get("document_count")),
        "chunk_count": coerce_non_negative_int_from_sqlite_numberish(row.get("chunk_count")),
        "queued": coerce_non_negative_int_from_sqlite_numberish(row.get("queued")),
        "fetching": coerce_non_negative_int_from_sqlite_numberish(row.get("fetching")),
        "parsing": coerce_non_negative_int_from_sqlite_numberish(row.get("parsing")),
        "chunking": coerce_non_negative_int_from_sqlite_numberish(row.get("chunking")),
        "embedding": coerce_non_negative_int_from_sqlite_numberish(row.get("embedding")),
        "completed": coerce_non_negative_int_from_sqlite_numberish(row.get("completed")),
        "error": coerce_non_negative_int_from_sqlite_numberish(row.get("error")),
    }


async def get_active_linked_rag_documents_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
) -> list[dict[str, str | int]]:
    rows = await query_to_dicts(
        database,
        """
        SELECT
            link.source_conv_id,
            link.source_user_id,
            link.source_document_id,
            link.source_knowledge_attachment_id,
            link.source_item_id,
            link.target_knowledge_attachment_id,
            link.target_item_id
        FROM rag_linked_documents link
        JOIN webui_conversation_knowledge_attachments summary
          ON summary.id = link.target_knowledge_attachment_id
         AND summary.conv_id = link.target_conv_id
         AND summary.user_id = link.target_user_id
        JOIN rag_documents document
          ON document.id = link.source_document_id
         AND document.conv_id = link.source_conv_id
         AND document.user_id = link.source_user_id
        WHERE link.target_conv_id = ?
          AND link.target_user_id = ?
          AND link.status = 'active'
          AND summary.state = 'committed'
          AND summary.source_type = 'linked_knowledge'
          AND document.status = 'completed'
        ORDER BY link.source_conv_id ASC, link.source_document_id ASC
        """,
        (conv_id, user_id),
    )
    linked_documents: list[dict[str, str | int]] = []
    for row in rows:
        source_conv_id = row.get("source_conv_id")
        source_user_id = row.get("source_user_id")
        source_document_id = row.get("source_document_id")
        source_knowledge_attachment_id = row.get("source_knowledge_attachment_id")
        source_item_id = row.get("source_item_id")
        target_knowledge_attachment_id = row.get("target_knowledge_attachment_id")
        target_item_id = row.get("target_item_id")
        if not isinstance(source_conv_id, str):
            continue
        if not isinstance(source_user_id, int):
            continue
        if not isinstance(source_document_id, str):
            continue
        if not isinstance(source_knowledge_attachment_id, str):
            continue
        if not isinstance(source_item_id, int):
            continue
        if not isinstance(target_knowledge_attachment_id, str):
            continue
        if not isinstance(target_item_id, int):
            continue
        linked_documents.append(
            {
                "source_conv_id": source_conv_id,
                "source_user_id": source_user_id,
                "source_document_id": source_document_id,
                "source_knowledge_attachment_id": source_knowledge_attachment_id,
                "source_item_id": source_item_id,
                "target_knowledge_attachment_id": target_knowledge_attachment_id,
                "target_item_id": target_item_id,
            },
        )
    return linked_documents
