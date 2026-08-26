"""SoAI - Knowledge attachment active item queries [backend/database/repositories/users/conversation_attachment_knowledge_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_ITEM_STATUSES,
)
from database.core.query_execution import query_to_dicts

__all__ = (
    "list_active_knowledge_attachment_task_ids_query",
    "sync_knowledge_attachment_has_active_items",
)


async def list_active_knowledge_attachment_task_ids_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> list[str]:
    rows = await query_to_dicts(
        database,
        """
        SELECT DISTINCT job.task_id
        FROM webui_conversation_knowledge_attachment_items item
        JOIN rag_processing_jobs job ON job.document_id = item.document_id
        WHERE item.conv_id = ?
          AND item.user_id = ?
          AND item.knowledge_attachment_id = ?
          AND job.status IN ('queued', 'running', 'retryable')
        ORDER BY job.task_id
        """,
        (conv_id, user_id, knowledge_attachment_id),
    )
    return [
        task_id.strip()
        for row in rows
        if isinstance((task_id := row.get("task_id")), str) and task_id.strip()
    ]


def sync_knowledge_attachment_has_active_items(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> bool:
    placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ITEM_STATUSES)
    row = conn.execute(
        f"""
        SELECT 1
        FROM webui_conversation_knowledge_attachment_items
        WHERE conv_id = ?
          AND user_id = ?
          AND knowledge_attachment_id = ?
          AND (rag_status IS NULL OR rag_status IN ({placeholders}))
        LIMIT 1
        """,
        (conv_id, user_id, knowledge_attachment_id, *KNOWLEDGE_ACTIVE_ITEM_STATUSES),
    ).fetchone()
    return row is not None
