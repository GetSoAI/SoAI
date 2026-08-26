"""SoAI - RAG document mutation queries [backend/database/repositories/files/rag_document_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from database.repositories.files.rag_linked_document_refresh import (
    sync_linked_source_document_ids_for_conversation,
    sync_refresh_linked_knowledge_for_source_documents,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_delete_rag_document",
    "sync_delete_rag_documents_for_conversation",
)


def sync_delete_rag_document(
    conn: sqlite3.Connection,
    doc_id: str,
    conv_id: str,
) -> tuple[bool, list[JSONDict]]:
    now = epoch_ms()
    cursor = conn.execute(
        "DELETE FROM rag_documents WHERE id = ? AND conv_id = ?",
        (doc_id, conv_id),
    )
    deleted = cursor.rowcount > 0
    remaining = conn.execute(
        "SELECT 1 FROM rag_documents WHERE id = ? LIMIT 1",
        (doc_id,),
    ).fetchone()
    confirmed_deleted = deleted and remaining is None
    if confirmed_deleted:
        linked_summaries = sync_refresh_linked_knowledge_for_source_documents(
            conn,
            source_document_ids=(doc_id,),
            updated_at_ms=now,
        )
    else:
        linked_summaries = []
    return confirmed_deleted, linked_summaries


def sync_delete_rag_documents_for_conversation(
    conn: sqlite3.Connection,
    conv_id: str,
) -> tuple[int, list[JSONDict]]:
    source_document_ids = sync_linked_source_document_ids_for_conversation(
        conn,
        source_conv_id=conv_id,
    )
    now = epoch_ms()
    cursor = conn.execute(
        "DELETE FROM rag_documents WHERE conv_id = ?",
        (conv_id,),
    )
    deleted_count = int(cursor.rowcount or 0)
    if deleted_count > 0:
        linked_summaries = sync_refresh_linked_knowledge_for_source_documents(
            conn,
            source_document_ids=source_document_ids,
            updated_at_ms=now,
        )
    else:
        linked_summaries = []
    return deleted_count, linked_summaries
