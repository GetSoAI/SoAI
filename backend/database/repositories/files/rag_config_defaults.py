"""SoAI - Atomic RAG configuration and user-default persistence [backend/database/repositories/files/rag_config_defaults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.chat.conversation_defaults import write_chat_conversation_defaults_rag_config
from core.database.requests import UpdateRAGConfigRequest, UpdateRAGConfigWithDefaultsRequest
from core.errors.exceptions import StateError
from core.files.database_types import RAGConfigWithDefaultsResult, RAGConversationConfigRecord
from core.rag.config_materialization import project_rag_config_record
from core.rag.preferences import write_chat_default_embedding_model
from core.types.json import JSONDict
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.files.rag_config import sync_update_rag_config
from database.repositories.files.record_parsing import parse_rag_conversation_config_record
from database.repositories.users.user_preference_mutations import sync_merge_user_preferences

__all__ = ("sync_update_rag_config_with_defaults",)


def _read_rag_config(
    conn: sqlite3.Connection,
    conv_id: str,
) -> RAGConversationConfigRecord:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """SELECT conv_id, enabled, retrieval_strategy, top_k, similarity_threshold,
               chunking_strategy, chunk_size, chunk_overlap, embedding_model, config_metadata,
               created_at_ms, last_modified_at_ms
               FROM rag_conversation_config WHERE conv_id = ?""",
            (conv_id,),
        )
    )
    if row is None:
        raise StateError("RAG configuration mutation did not produce a row.")
    return parse_rag_conversation_config_record(row)


def _current_embedding_selector(conn: sqlite3.Connection, conv_id: str) -> str | None:
    row = conn.execute(
        "SELECT embedding_model FROM rag_conversation_config WHERE conv_id = ?",
        (conv_id,),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    if not isinstance(row[0], str):
        raise StateError("Stored RAG embedding selector is invalid.")
    return row[0]


def _config_changes(
    config: RAGConversationConfigRecord,
    request: UpdateRAGConfigRequest,
) -> bool:
    compared_values = (
        (request.enabled, config["enabled"]),
        (request.retrieval_strategy, config["retrieval_strategy"]),
        (request.top_k, config["top_k"]),
        (request.similarity_threshold, config["similarity_threshold"]),
        (request.chunking_strategy, config["chunking_strategy"]),
        (request.chunk_size, config["chunk_size"]),
        (request.chunk_overlap, config["chunk_overlap"]),
        (request.embedding_model, config["embedding_model"]),
        (request.config_metadata, config["config_metadata"]),
    )
    return any(
        requested is not None and requested != stored for requested, stored in compared_values
    )


def sync_update_rag_config_with_defaults(
    conn: sqlite3.Connection,
    request: UpdateRAGConfigWithDefaultsRequest,
) -> RAGConfigWithDefaultsResult:
    update = request.update
    if request.require_matching_embedding_selector:
        current_selector = _current_embedding_selector(conn, update.conv_id)
        if current_selector != request.expected_embedding_selector:
            current = _read_rag_config(conn, update.conv_id)
            return RAGConfigWithDefaultsResult(config=current, superseded=True)
    existing = conn.execute(
        "SELECT 1 FROM rag_conversation_config WHERE conv_id = ?",
        (update.conv_id,),
    ).fetchone()
    config = _read_rag_config(conn, update.conv_id) if existing is not None else None
    if config is None or _config_changes(config, update):
        sync_update_rag_config(
            conn,
            update.conv_id,
            update.enabled,
            update.retrieval_strategy,
            update.top_k,
            update.similarity_threshold,
            update.chunking_strategy,
            update.chunk_size,
            update.chunk_overlap,
            update.embedding_model,
            update.config_metadata,
        )
        config = _read_rag_config(conn, update.conv_id)
    preference_patch: JSONDict = {}
    write_chat_conversation_defaults_rag_config(
        preference_patch,
        project_rag_config_record(config),
    )
    if update.embedding_model is not None:
        write_chat_default_embedding_model(preference_patch, update.embedding_model)
    preferences = sync_merge_user_preferences(conn, request.user_id, preference_patch)
    if preferences is None:
        raise StateError("RAG configuration owner is unavailable.")
    return RAGConfigWithDefaultsResult(
        config=config,
        superseded=False,
        preferences=preferences,
    )
