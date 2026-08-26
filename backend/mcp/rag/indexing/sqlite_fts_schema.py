"""SoAI - SQLite FTS5 schema readiness for MCP RAG [backend/mcp/rag/indexing/sqlite_fts_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import DatabaseError, StateError
from core.rag.sparse_index_errors import SparseIndexRebuildRequiredError

__all__ = (
    "ensure_fts_schema_ready",
    "get_fts_meta_value",
    "reset_fts_schema",
    "set_fts_meta_value",
    "set_fts_required_meta",
)


def create_fts_schema(connection: sqlite3.Connection, tokenizer: str) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS chunk_map (chunk_id TEXT PRIMARY KEY, rowid INTEGER UNIQUE)",
    )
    connection.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, content, tokenize='{tokenizer}')",
    )


def reset_fts_schema(connection: sqlite3.Connection, tokenizer: str) -> None:
    connection.execute("DROP TABLE IF EXISTS chunks_fts")
    connection.execute("DROP TABLE IF EXISTS chunk_map")
    connection.execute("DROP TABLE IF EXISTS meta")
    create_fts_schema(connection, tokenizer)


def get_fts_meta_value(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def set_fts_meta_value(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def set_fts_required_meta(
    connection: sqlite3.Connection,
    *,
    tokenizer: str,
    stopwords_mode: str,
) -> None:
    set_fts_meta_value(connection, "tokenizer", str(tokenizer))
    set_fts_meta_value(connection, "stopwords_mode", str(stopwords_mode))


def _count_chunk_map_rows(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM chunk_map").fetchone()
    return int(row[0]) if row else 0


def _count_chunks_fts_rows(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()
    return int(row[0]) if row else 0


def _ensure_schema_exists(connection: sqlite3.Connection, tokenizer: str) -> None:
    try:
        create_fts_schema(connection, tokenizer)
    except sqlite3.OperationalError as exception:
        message = str(exception).lower()
        if "fts5" in message:
            raise StateError(
                "SQLite FTS5 is not available in this Python/SQLite build.",
            ) from exception
        raise DatabaseError(
            f"Database operational error: {exception}",
            operation="mcp.index.initialize",
            cause=exception,
        ) from exception


def ensure_fts_schema_ready(
    connection: sqlite3.Connection,
    *,
    tokenizer: str,
    stopwords_mode: str,
) -> None:
    _ensure_schema_exists(connection, tokenizer)
    existing_tokenizer = get_fts_meta_value(connection, "tokenizer")
    existing_stopwords = get_fts_meta_value(connection, "stopwords_mode")
    if existing_tokenizer is None or existing_stopwords is None:
        if _count_chunk_map_rows(connection) == 0 and _count_chunks_fts_rows(connection) == 0:
            set_fts_required_meta(
                connection,
                tokenizer=tokenizer,
                stopwords_mode=stopwords_mode,
            )
            set_fts_meta_value(connection, "chunk_count", "0")
            return
        raise SparseIndexRebuildRequiredError("Sparse index metadata missing; rebuild required.")
    if str(existing_tokenizer) != tokenizer or str(existing_stopwords) != stopwords_mode:
        raise SparseIndexRebuildRequiredError("Sparse index settings changed; rebuild required.")
