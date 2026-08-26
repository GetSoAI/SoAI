"""SoAI - SQLite FTS5 full-text search index for MCP RAG [backend/mcp/rag/indexing/sqlite_fts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from typing import ClassVar

from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.rag.bm25_options import (
    BM25_EN_STOPWORDS,
    BM25_STOPWORD_MODES,
    BM25_TOKENIZERS,
    DEFAULT_BM25_STOPWORDS_MODE,
    DEFAULT_BM25_TOKENIZER,
)
from core.sqlite.connections import connect_sqlite
from core.sqlite.file_permissions import secure_sqlite_file_permissions
from core.sqlite.policy import SQLITE_FTS_PRAGMAS, configure_sqlite_connection
from mcp.rag.indexing.sqlite_fts_schema import (
    ensure_fts_schema_ready,
    get_fts_meta_value,
    reset_fts_schema,
    set_fts_meta_value,
    set_fts_required_meta,
)

__all__ = ("SQLiteFTS5BM25Index",)


@dataclass(frozen=True, slots=True)
class SQLiteFTS5BM25Index:
    db_path: str
    tokenizer: str = DEFAULT_BM25_TOKENIZER
    stopwords_mode: str = DEFAULT_BM25_STOPWORDS_MODE
    _TOKEN_RE: ClassVar[re.Pattern[str]] = re.compile(r"[\w]+", re.UNICODE)

    def __post_init__(self) -> None:
        if not isinstance(self.db_path, str) or not self.db_path.strip():
            raise ValidationError("db_path must be a non-empty string")
        if "\x00" in self.db_path:
            raise ValidationError("db_path contains NUL byte")
        if not os.path.isabs(self.db_path):
            raise ValidationError("db_path must be an absolute path")
        db_dir = os.path.dirname(self.db_path)
        if not db_dir:
            raise ValidationError("db_path must include a parent directory")
        if self.tokenizer not in BM25_TOKENIZERS:
            raise ValidationError(f"Unsupported tokenizer: {self.tokenizer!r}")
        if self.stopwords_mode not in BM25_STOPWORD_MODES:
            raise ValidationError(f"Unsupported stopwords_mode: {self.stopwords_mode!r}")

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        secure_sqlite_file_permissions(self.db_path, create_missing=True)
        connection = connect_sqlite(self.db_path, timeout=30, isolation_level=None)
        configure_sqlite_connection(connection, SQLITE_FTS_PRAGMAS)
        return connection

    def ensure_ready(self) -> None:
        connection = self._connect()
        try:
            self._ensure_ready_on_connection(connection)
        finally:
            connection.close()

    def _ensure_ready_on_connection(self, connection: sqlite3.Connection) -> None:
        ensure_fts_schema_ready(
            connection,
            tokenizer=self.tokenizer,
            stopwords_mode=self.stopwords_mode,
        )

    def recorded_chunk_count(self) -> int | None:
        if not os.path.exists(self.db_path):
            return None
        connection = self._connect()
        try:
            value = get_fts_meta_value(connection, "chunk_count")
            if value is None:
                return None
            return int(value)
        finally:
            connection.close()

    def _stopwords_set(self) -> set[str]:
        if self.stopwords_mode == "en":
            return set(BM25_EN_STOPWORDS)
        return set()

    def _query_tokens(self, query: str) -> list[str]:
        tokens = [token.lower() for token in self._TOKEN_RE.findall(query.lower())]
        stopwords = self._stopwords_set()
        if not stopwords:
            return tokens
        return [token for token in tokens if token not in stopwords]

    def _apply_stopwords_to_content(self, content: str) -> str:
        stopwords = self._stopwords_set()
        if not stopwords:
            return content
        tokens = [token.lower() for token in self._TOKEN_RE.findall(content.lower())]
        filtered = [token for token in tokens if token not in stopwords]
        return " ".join(filtered)

    def _fts_match_query(self, query: str) -> str:
        tokens = self._query_tokens(query)
        if not tokens:
            return ""
        return " OR ".join(tokens)

    def rebuild(self, documents: list[tuple[str, str]]) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN")
            reset_fts_schema(connection, self.tokenizer)
            set_fts_required_meta(
                connection,
                tokenizer=self.tokenizer,
                stopwords_mode=self.stopwords_mode,
            )
            for chunk_id, content in documents:
                connection.execute(
                    "INSERT INTO chunks_fts(chunk_id, content) VALUES (?, ?)",
                    (chunk_id, self._apply_stopwords_to_content(content)),
                )
                rowid = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                connection.execute(
                    "INSERT INTO chunk_map(chunk_id, rowid) VALUES (?, ?)",
                    (chunk_id, rowid),
                )
            set_fts_meta_value(connection, "chunk_count", str(len(documents)))
            connection.execute("COMMIT")
        except RECOVERABLE_EXCEPTIONS:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def add_documents(self, documents: list[tuple[str, str]]) -> None:
        if not documents:
            return
        connection = self._connect()
        try:
            self._ensure_ready_on_connection(connection)
            connection.execute("BEGIN")
            try:
                for chunk_id, content in documents:
                    processed_content = self._apply_stopwords_to_content(content)
                    row = connection.execute(
                        "SELECT rowid FROM chunk_map WHERE chunk_id = ?",
                        (chunk_id,),
                    ).fetchone()
                    if row:
                        rowid = int(row[0])
                        connection.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
                        connection.execute(
                            "INSERT INTO chunks_fts(rowid, chunk_id, content) VALUES (?, ?, ?)",
                            (rowid, chunk_id, processed_content),
                        )
                    else:
                        connection.execute(
                            "INSERT INTO chunks_fts(chunk_id, content) VALUES (?, ?)",
                            (chunk_id, processed_content),
                        )
                        rowid = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
                        connection.execute(
                            "INSERT INTO chunk_map(chunk_id, rowid) VALUES (?, ?)",
                            (chunk_id, rowid),
                        )
                row = connection.execute("SELECT COUNT(*) FROM chunk_map").fetchone()
                set_fts_meta_value(connection, "chunk_count", str(int(row[0]) if row else 0))
                connection.execute("COMMIT")
            except RECOVERABLE_EXCEPTIONS:
                connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()

    def remove_documents(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        if not os.path.exists(self.db_path):
            return
        connection = self._connect()
        try:
            self._ensure_ready_on_connection(connection)
            connection.execute("BEGIN")
            try:
                for chunk_id in chunk_ids:
                    row = connection.execute(
                        "SELECT rowid FROM chunk_map WHERE chunk_id = ?",
                        (chunk_id,),
                    ).fetchone()
                    if not row:
                        continue
                    rowid = int(row[0])
                    connection.execute("DELETE FROM chunks_fts WHERE rowid = ?", (rowid,))
                    connection.execute("DELETE FROM chunk_map WHERE chunk_id = ?", (chunk_id,))
                row = connection.execute("SELECT COUNT(*) FROM chunk_map").fetchone()
                set_fts_meta_value(connection, "chunk_count", str(int(row[0]) if row else 0))
                connection.execute("COMMIT")
            except RECOVERABLE_EXCEPTIONS:
                connection.execute("ROLLBACK")
                raise
        finally:
            connection.close()

    def search(
        self,
        query: str,
        top_k: int = 10,
        chunk_id_prefix: str | None = None,
    ) -> list[tuple[str, float]]:
        if not os.path.exists(self.db_path):
            return []
        match_query = self._fts_match_query(query)
        if not match_query or top_k <= 0:
            return []
        prefix = chunk_id_prefix
        if prefix is not None and not isinstance(prefix, str):
            raise ValidationError("chunk_id_prefix must be a string or None")
        if isinstance(prefix, str):
            prefix = prefix.strip()
            if "\x00" in prefix:
                raise ValidationError("chunk_id_prefix contains NUL byte")
            if not prefix:
                prefix = None
        connection = self._connect()
        try:
            self._ensure_ready_on_connection(connection)
            if prefix is None:
                rows = connection.execute(
                    "SELECT chunk_id, -bm25(chunks_fts) AS score FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
                    (match_query, int(top_k)),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT chunk_id, -bm25(chunks_fts) AS score FROM chunks_fts WHERE chunks_fts MATCH ? AND chunk_id GLOB ? ORDER BY bm25(chunks_fts) LIMIT ?",
                    (match_query, f"{prefix}*", int(top_k)),
                ).fetchall()
        finally:
            connection.close()
        return [(str(row[0]), float(row[1])) for row in rows if row and row[0]]
