"""SoAI - Database RAG document operations [backend/database/repositories/files/rag_documents.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError, StateError
from core.files.database_types import RAGDocumentRecord
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.files.record_parsing import parse_rag_document_record
from database.repositories.users.conversation_attachment_knowledge_items import (
    sync_add_knowledge_attachment_item,
)

__all__ = ("sync_create_rag_document", "sync_create_rag_document_with_knowledge_item")


def _require_knowledge_item_created(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    document_id: str,
) -> None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT 1
            FROM webui_conversation_knowledge_attachment_items
            WHERE conv_id = ?
              AND user_id = ?
              AND knowledge_attachment_id = ?
              AND document_id = ?
            LIMIT 1
            """,
            (conv_id, user_id, knowledge_attachment_id, document_id),
        ),
    )
    if row is None:
        raise ConflictError("RAG document knowledge attachment item was not created.")


def sync_create_rag_document(
    conn: sqlite3.Connection,
    doc_id: str,
    conv_id: str,
    user_id: int,
    file_id: str | None,
    filename: str,
    file_type: str,
    file_size_bytes: int,
    status: str,
    source_type: str,
    source_url: str | None,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str | None,
    metadata: JSONDict | None,
) -> RAGDocumentRecord:
    now = epoch_ms()
    metadata_json = serialize_json_compact_stable_strict(metadata) if metadata is not None else None
    conn.execute(
        """INSERT INTO rag_documents (
            id, conv_id, user_id, file_id, filename, file_type, file_size_bytes,
            status, source_type, source_url, chunking_strategy, chunk_size, chunk_overlap,
            embedding_model, metadata, created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            doc_id,
            conv_id,
            user_id,
            file_id,
            filename,
            file_type,
            file_size_bytes,
            status,
            source_type,
            source_url,
            chunking_strategy,
            chunk_size,
            chunk_overlap,
            embedding_model,
            metadata_json,
            now,
        ),
    )
    cursor = conn.execute("SELECT * FROM rag_documents WHERE id = ?", (doc_id,))
    row = sync_fetch_one_as_dict(cursor)
    if not row:
        raise StateError(f"RAG document {doc_id} not found after INSERT")
    return parse_rag_document_record(row)


def sync_create_rag_document_with_knowledge_item(
    conn: sqlite3.Connection,
    doc_id: str,
    conv_id: str,
    user_id: int,
    file_id: str | None,
    filename: str,
    file_type: str,
    file_size_bytes: int,
    status: str,
    source_type: str,
    source_url: str | None,
    chunking_strategy: str,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str | None,
    metadata: JSONDict | None,
    knowledge_attachment_id: str,
    item_index: int,
    operation_type: str,
) -> tuple[RAGDocumentRecord, JSONDict]:
    record = sync_create_rag_document(
        conn,
        doc_id,
        conv_id,
        user_id,
        file_id,
        filename,
        file_type,
        file_size_bytes,
        status,
        source_type,
        source_url,
        chunking_strategy,
        chunk_size,
        chunk_overlap,
        embedding_model,
        metadata,
    )
    summary = sync_add_knowledge_attachment_item(
        conn,
        conv_id,
        user_id,
        knowledge_attachment_id,
        doc_id,
        None,
        item_index,
        filename,
        file_type,
        file_size_bytes,
        status,
        operation_type,
        None,
        epoch_ms(),
    )
    _require_knowledge_item_created(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        document_id=doc_id,
    )
    return record, summary
