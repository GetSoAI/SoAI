"""SoAI - RAG conversation config and vector collection queries [backend/database/repositories/files/rag_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.files.database_types import (
    RAGConversationConfigRecord,
    RAGVectorCollectionMetadataRecord,
)
from core.rag.config_values import RAG_CONFIG_VALUE_FIELDS
from core.timing.epoch import epoch_ms
from database.core.json_codec import serialize_optional_json_object_field
from database.core.query_execution import query_to_dicts, sync_fetch_one_as_dict
from database.core.sql_builders import build_update_statement
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row
from database.repositories.files.record_parsing import (
    parse_rag_conversation_config_record,
    parse_rag_vector_collection_metadata_record,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "get_rag_collection_metadata_query",
    "get_rag_config_query",
    "sync_activate_rag_collection",
    "sync_delete_rag_collection_metadata_for_conversation",
    "sync_update_rag_collection_metadata",
    "sync_update_rag_config",
)


async def get_rag_config_query(
    database: aiosqlite.Connection,
    conv_id: str,
) -> RAGConversationConfigRecord | None:
    rows = await query_to_dicts(
        database,
        """SELECT conv_id, enabled, retrieval_strategy, top_k, similarity_threshold,
           chunking_strategy, chunk_size, chunk_overlap, embedding_model, config_metadata,
           created_at_ms, last_modified_at_ms
           FROM rag_conversation_config WHERE conv_id = ?""",
        (conv_id,),
    )
    if not rows:
        return None
    return parse_rag_conversation_config_record(rows[0])


async def get_rag_collection_metadata_query(
    database: aiosqlite.Connection,
    conv_id: str,
) -> RAGVectorCollectionMetadataRecord | None:
    rows = await query_to_dicts(
        database,
        """SELECT id, conv_id, collection_name, embedding_model, embedding_dimensions,
           document_count, chunk_count, created_at_ms, last_synced_at_ms, metadata
           FROM rag_vector_collections
           WHERE conv_id = ?
           ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END, last_synced_at_ms DESC
           LIMIT 1""",
        (conv_id, conv_id),
    )
    if not rows:
        return None
    return parse_rag_vector_collection_metadata_record(rows[0])


def sync_delete_rag_collection_metadata_for_conversation(
    conn: sqlite3.Connection,
    conv_id: str,
) -> None:
    conv_id_value = conv_id.strip()
    if not conv_id_value:
        return
    conn.execute("DELETE FROM rag_vector_collections WHERE conv_id = ?", (conv_id_value,))


def sync_update_rag_config(
    conn: sqlite3.Connection,
    conv_id: str,
    enabled: bool | None = None,
    retrieval_strategy: str | None = None,
    top_k: int | None = None,
    similarity_threshold: float | None = None,
    chunking_strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    embedding_model: str | None = None,
    config_metadata: JSONDict | None = None,
) -> None:
    now = epoch_ms()
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM rag_conversation_config WHERE conv_id = ?",
            (conv_id,),
        ),
    )
    exists = bool(row and coerce_required_int_from_sqlite_row(row, "count") > 0)
    if not exists:
        conn.execute(
            """INSERT INTO rag_conversation_config (
                conv_id, enabled, retrieval_strategy, top_k, similarity_threshold,
                chunking_strategy, chunk_size, chunk_overlap, embedding_model, config_metadata,
                created_at_ms, last_modified_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                conv_id,
                1 if enabled is None else int(enabled),
                retrieval_strategy if retrieval_strategy is not None else "similarity",
                top_k if top_k is not None else 5,
                similarity_threshold if similarity_threshold is not None else 0.3,
                chunking_strategy if chunking_strategy is not None else "token_based",
                chunk_size if chunk_size is not None else 500,
                chunk_overlap if chunk_overlap is not None else 100,
                embedding_model,
                serialize_optional_json_object_field(
                    config_metadata,
                    error_message="rag_conversation_config.config_metadata must be a JSON object.",
                ),
                now,
                now,
            ),
        )
    else:
        updates: dict[str, SQLiteValue] = {"last_modified_at_ms": now}
        if enabled is not None:
            updates["enabled"] = int(enabled)
        if retrieval_strategy is not None:
            updates["retrieval_strategy"] = retrieval_strategy
        if top_k is not None:
            updates["top_k"] = top_k
        if similarity_threshold is not None:
            updates["similarity_threshold"] = similarity_threshold
        if chunking_strategy is not None:
            updates["chunking_strategy"] = chunking_strategy
        if chunk_size is not None:
            updates["chunk_size"] = chunk_size
        if chunk_overlap is not None:
            updates["chunk_overlap"] = chunk_overlap
        if embedding_model is not None:
            updates["embedding_model"] = embedding_model
        if config_metadata is not None:
            updates["config_metadata"] = serialize_optional_json_object_field(
                config_metadata,
                error_message="rag_conversation_config.config_metadata must be a JSON object.",
            )
        sql, params = build_update_statement(
            table="rag_conversation_config",
            updates=updates,
            where_clause="conv_id = ?",
            where_params=(conv_id,),
            allowed_columns=set(RAG_CONFIG_VALUE_FIELDS)
            | {"last_modified_at_ms", "config_metadata"},
        )
        conn.execute(sql, params)


def sync_update_rag_collection_metadata(
    conn: sqlite3.Connection,
    collection_id: str,
    conv_id: str,
    collection_name: str,
    embedding_model: str,
    embedding_dimensions: int,
    document_count: int,
    chunk_count: int,
    metadata: JSONDict | None = None,
) -> None:
    now = epoch_ms()
    config_row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM rag_conversation_config WHERE conv_id = ?",
            (conv_id,),
        ),
    )
    if config_row is None or coerce_required_int_from_sqlite_row(config_row, "count") == 0:
        conn.execute(
            """
            INSERT INTO rag_conversation_config (
                conv_id, enabled, created_at_ms, last_modified_at_ms
            ) VALUES (?, 0, ?, ?)
            """,
            (conv_id, now, now),
        )
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM rag_vector_collections WHERE id = ?",
            (collection_id,),
        ),
    )
    exists = bool(row and coerce_required_int_from_sqlite_row(row, "count") > 0)
    if not exists:
        conn.execute(
            """INSERT INTO rag_vector_collections (
                id, conv_id, collection_name, embedding_model, embedding_dimensions,
                document_count, chunk_count, created_at_ms, last_synced_at_ms, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                collection_id,
                conv_id,
                collection_name,
                embedding_model,
                embedding_dimensions,
                document_count,
                chunk_count,
                now,
                now,
                serialize_optional_json_object_field(
                    metadata,
                    error_message="rag_vector_collections.metadata must be a JSON object.",
                ),
            ),
        )
    else:
        conn.execute(
            """UPDATE rag_vector_collections SET
               conv_id = ?, collection_name = ?, embedding_model = ?, embedding_dimensions = ?,
               document_count = ?, chunk_count = ?, last_synced_at_ms = ?, metadata = ?
               WHERE id = ?""",
            (
                conv_id,
                collection_name,
                embedding_model,
                embedding_dimensions,
                document_count,
                chunk_count,
                now,
                serialize_optional_json_object_field(
                    metadata,
                    error_message="rag_vector_collections.metadata must be a JSON object.",
                ),
                collection_id,
            ),
        )


def sync_activate_rag_collection(
    conn: sqlite3.Connection,
    collection_id: str,
    conv_id: str,
    collection_name: str,
    embedding_model: str,
    embedding_dimensions: int,
    document_count: int,
    chunk_count: int,
    metadata: JSONDict | None,
) -> None:
    sync_update_rag_collection_metadata(
        conn,
        collection_id,
        conv_id,
        collection_name,
        embedding_model,
        embedding_dimensions,
        document_count,
        chunk_count,
        metadata,
    )
    sync_update_rag_config(
        conn,
        conv_id,
        embedding_model=embedding_model,
    )
