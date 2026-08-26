"""SoAI - Database RAG chunk operations [backend/database/repositories/files/rag_chunks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.files.database_types import RAGChunkRecord, RAGConversationChunkPreview
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.validation.coercion import coerce_int_strict
from core.validation.requirements import coerce_optional_int
from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite_numberish
from database.repositories.files.record_parsing import (
    parse_rag_chunk_record,
    parse_rag_conversation_chunk_preview,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "get_rag_chunk_by_id_query",
    "get_rag_chunks_by_ids_completed_query",
    "get_rag_chunks_for_conversation_query",
    "get_rag_chunks_for_conversation_page_query",
    "get_rag_chunks_for_document_query",
    "get_rag_chunks_for_document_cleanup_query",
    "get_rag_chunks_for_document_page_query",
    "get_rag_counts_for_conversation_query",
    "sync_create_rag_chunks",
    "sync_replace_rag_chunks_for_job",
)


def sync_create_rag_chunks(
    conn: sqlite3.Connection,
    chunks: list[JSONDict],
) -> None:
    now = epoch_ms()
    params: list[tuple[SQLiteValue, ...]] = []
    for chunk in chunks:
        metadata = chunk.get("metadata")
        params.append(
            (
                str(chunk.get("id") or ""),
                str(chunk.get("document_id") or ""),
                coerce_int_strict(chunk.get("chunk_index")),
                str(chunk.get("content") or ""),
                str(chunk.get("content_hash") or ""),
                coerce_optional_int(chunk.get("token_count")),
                coerce_optional_int(chunk.get("start_char")),
                coerce_optional_int(chunk.get("end_char")),
                (
                    serialize_json_compact_stable_strict(metadata)
                    if isinstance(metadata, dict)
                    else None
                ),
                now,
            ),
        )
    conn.executemany(
        """INSERT INTO rag_chunks (
            id, document_id, chunk_index, content, content_hash, token_count,
            start_char, end_char, metadata, created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        params,
    )


def sync_replace_rag_chunks_for_job(
    conn: sqlite3.Connection,
    job_id: str,
    lease_token: str,
    document_id: str,
    chunks: list[JSONDict],
) -> bool:
    now = epoch_ms()
    row = conn.execute(
        """
        SELECT 1
        FROM rag_processing_jobs
        WHERE job_id = ? AND document_id = ? AND lease_token = ? AND status = 'running'
          AND lease_expires_at_ms IS NOT NULL AND lease_expires_at_ms >= ?
        LIMIT 1
        """,
        (job_id, document_id, lease_token, now),
    ).fetchone()
    if row is None:
        return False
    conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
    sync_create_rag_chunks(conn, chunks)
    return True


async def get_rag_chunks_for_document_query(
    database: aiosqlite.Connection,
    document_id: str,
) -> list[RAGChunkRecord]:
    rows = await query_to_dicts(
        database,
        """SELECT c.id, c.document_id, c.chunk_index, c.content, c.content_hash,
           c.token_count, c.start_char, c.end_char, c.metadata, c.created_at_ms
           FROM rag_chunks c
           JOIN rag_documents d ON c.document_id = d.id
           WHERE c.document_id = ? AND d.status = 'completed'
           ORDER BY c.chunk_index ASC""",
        (document_id,),
    )
    return [parse_rag_chunk_record(row) for row in rows]


async def get_rag_chunks_for_document_cleanup_query(
    database: aiosqlite.Connection,
    document_id: str,
) -> list[RAGChunkRecord]:
    rows = await query_to_dicts(
        database,
        """SELECT id, document_id, chunk_index, content, content_hash, token_count,
           start_char, end_char, metadata, created_at_ms
           FROM rag_chunks WHERE document_id = ? ORDER BY chunk_index ASC""",
        (document_id,),
    )
    return [parse_rag_chunk_record(row) for row in rows]


async def get_rag_chunks_for_document_page_query(
    database: aiosqlite.Connection,
    document_id: str,
    *,
    after_chunk_index: int | None,
    limit: int,
) -> list[RAGChunkRecord]:
    params: list[SQLiteValue] = [document_id]
    after_clause = ""
    if after_chunk_index is not None:
        after_clause = "AND c.chunk_index > ?"
        params.append(after_chunk_index)
    params.append(max(1, int(limit)))
    rows = await query_to_dicts(
        database,
        f"""SELECT c.id, c.document_id, c.chunk_index, c.content, c.content_hash,
           c.token_count, c.start_char, c.end_char, c.metadata, c.created_at_ms
           FROM rag_chunks c
           JOIN rag_documents d ON c.document_id = d.id
           WHERE c.document_id = ? AND d.status = 'completed' {after_clause}
           ORDER BY c.chunk_index ASC
           LIMIT ?""",
        tuple(params),
    )
    return [parse_rag_chunk_record(row) for row in rows]


async def get_rag_chunk_by_id_query(
    database: aiosqlite.Connection,
    chunk_id: str,
) -> RAGChunkRecord | None:
    rows = await query_to_dicts(
        database,
        """SELECT c.id, c.document_id, c.chunk_index, c.content, c.content_hash,
           c.token_count, c.start_char, c.end_char, c.metadata, c.created_at_ms
           FROM rag_chunks c
           JOIN rag_documents d ON c.document_id = d.id
           WHERE c.id = ? AND d.status = 'completed'""",
        (chunk_id,),
    )
    if not rows:
        return None
    return parse_rag_chunk_record(rows[0])


async def get_rag_chunks_by_ids_completed_query(
    database: aiosqlite.Connection,
    chunk_ids: list[str],
) -> list[RAGChunkRecord]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" for _ in chunk_ids)
    rows = await query_to_dicts(
        database,
        f"""SELECT c.id, c.document_id, c.chunk_index, c.content, c.content_hash,
           c.token_count, c.start_char, c.end_char, c.metadata, c.created_at_ms
           FROM rag_chunks c
           JOIN rag_documents d ON c.document_id = d.id
           WHERE c.id IN ({placeholders}) AND d.status = 'completed'""",
        tuple(chunk_ids),
    )
    return [parse_rag_chunk_record(row) for row in rows]


async def get_rag_chunks_for_conversation_query(
    database: aiosqlite.Connection,
    conv_id: str,
) -> list[RAGConversationChunkPreview]:
    rows = await query_to_dicts(
        database,
        """SELECT c.id, c.document_id, c.chunk_index, c.content, c.token_count,
           c.start_char, c.end_char
           FROM rag_chunks c
           JOIN rag_documents d ON c.document_id = d.id
           WHERE d.conv_id = ? AND d.status = 'completed'
           ORDER BY d.created_at_ms DESC, c.document_id ASC, c.chunk_index ASC""",
        (conv_id,),
    )
    return [parse_rag_conversation_chunk_preview(row) for row in rows]


async def get_rag_chunks_for_conversation_page_query(
    database: aiosqlite.Connection,
    conv_id: str,
    *,
    after_document_id: str | None,
    after_chunk_index: int | None,
    limit: int,
) -> list[RAGConversationChunkPreview]:
    params: list[SQLiteValue] = [conv_id]
    after_clause = ""
    if after_document_id is not None and after_chunk_index is not None:
        after_clause = "AND (c.document_id > ? OR (c.document_id = ? AND c.chunk_index > ?))"
        params.extend((after_document_id, after_document_id, after_chunk_index))
    params.append(max(1, int(limit)))
    rows = await query_to_dicts(
        database,
        f"""SELECT c.id, c.document_id, c.chunk_index, c.content, c.token_count,
           c.start_char, c.end_char
           FROM rag_chunks c
           JOIN rag_documents d ON c.document_id = d.id
           WHERE d.conv_id = ? AND d.status = 'completed' {after_clause}
           ORDER BY c.document_id ASC, c.chunk_index ASC
           LIMIT ?""",
        tuple(params),
    )
    return [parse_rag_conversation_chunk_preview(row) for row in rows]


async def get_rag_counts_for_conversation_query(
    database: aiosqlite.Connection,
    conv_id: str,
) -> dict[str, int]:
    rows = await query_to_dicts(
        database,
        """SELECT
             COUNT(*) AS document_count,
             SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
             SUM(CASE WHEN status = 'fetching' THEN 1 ELSE 0 END) AS fetching,
             SUM(CASE WHEN status = 'parsing' THEN 1 ELSE 0 END) AS parsing,
             SUM(CASE WHEN status = 'chunking' THEN 1 ELSE 0 END) AS chunking,
             SUM(CASE WHEN status = 'embedding' THEN 1 ELSE 0 END) AS embedding,
             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
             SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error,
             (SELECT COUNT(*)
              FROM rag_chunks c
              JOIN rag_documents d ON c.document_id = d.id
              WHERE d.conv_id = ? AND d.status = 'completed') AS chunk_count
           FROM rag_documents
           WHERE conv_id = ?""",
        (conv_id, conv_id),
    )
    if not rows:
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
    row = rows[0]
    document_count = coerce_non_negative_int_from_sqlite_numberish(row.get("document_count"))
    chunk_count = coerce_non_negative_int_from_sqlite_numberish(row.get("chunk_count"))
    queued = coerce_non_negative_int_from_sqlite_numberish(row.get("queued"))
    fetching = coerce_non_negative_int_from_sqlite_numberish(row.get("fetching"))
    parsing = coerce_non_negative_int_from_sqlite_numberish(row.get("parsing"))
    chunking = coerce_non_negative_int_from_sqlite_numberish(row.get("chunking"))
    embedding = coerce_non_negative_int_from_sqlite_numberish(row.get("embedding"))
    completed = coerce_non_negative_int_from_sqlite_numberish(row.get("completed"))
    error = coerce_non_negative_int_from_sqlite_numberish(row.get("error"))
    return {
        "document_count": document_count,
        "chunk_count": chunk_count,
        "queued": queued,
        "fetching": fetching,
        "parsing": parsing,
        "chunking": chunking,
        "embedding": embedding,
        "completed": completed,
        "error": error,
    }
