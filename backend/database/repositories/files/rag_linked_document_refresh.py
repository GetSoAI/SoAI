"""SoAI - RAG linked document refresh queries [backend/database/repositories/files/rag_linked_document_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.core.query_execution import sync_fetch_all_first_column
from database.repositories.users.conversation_linked_knowledge_activation import (
    sync_refresh_linked_knowledge_availability,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_linked_source_document_ids_for_conversation",
    "sync_refresh_linked_knowledge_for_source_documents",
)


def sync_refresh_linked_knowledge_for_source_documents(
    conn: sqlite3.Connection,
    *,
    source_document_ids: tuple[str, ...],
    updated_at_ms: int,
) -> list[JSONDict]:
    if not source_document_ids:
        return []
    placeholders = ",".join("?" for _ in source_document_ids)
    rows = sync_fetch_all_first_column(
        conn.execute(
            f"""
            SELECT DISTINCT target_knowledge_attachment_id
            FROM rag_linked_documents
            WHERE source_document_id IN ({placeholders})
            """,
            source_document_ids,
        ),
    )
    summaries: list[JSONDict] = []
    for value in rows:
        if isinstance(value, str) and value.strip():
            summary = sync_refresh_linked_knowledge_availability(
                conn,
                target_knowledge_attachment_id=value,
                updated_at_ms=updated_at_ms,
            )
            if summary is not None:
                summaries.append(summary)
    return summaries


def sync_linked_source_document_ids_for_conversation(
    conn: sqlite3.Connection,
    *,
    source_conv_id: str,
) -> tuple[str, ...]:
    rows = sync_fetch_all_first_column(
        conn.execute(
            """
            SELECT DISTINCT source_document_id
            FROM rag_linked_documents
            WHERE source_conv_id = ?
            """,
            (source_conv_id,),
        ),
    )
    return tuple(value for value in rows if isinstance(value, str) and value.strip())
