"""SoAI - Knowledge attachment terminal count mutation helpers [backend/database/repositories/users/conversation_attachment_knowledge_terminal_counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_ITEM_STATUSES,
)
from database.core.query_execution import sync_fetch_all_as_dicts

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("mark_active_items_terminal", "terminal_status_counts")


def terminal_status_counts(
    conn: sqlite3.Connection,
    *,
    knowledge_attachment_id: str,
    terminal_item_status: str,
    total_count: int,
) -> JSONDict:
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            """
            SELECT rag_status, COUNT(*) AS count
            FROM webui_conversation_knowledge_attachment_items
            WHERE knowledge_attachment_id = ?
            GROUP BY rag_status
            """,
            (knowledge_attachment_id,),
        ),
    )
    status_counts: JSONDict = {}
    moved_active_count = 0
    for row in rows:
        status = row.get("rag_status")
        count = row.get("count")
        if not isinstance(count, int) or count <= 0:
            continue
        if status is None:
            moved_active_count += count
            continue
        if isinstance(status, str):
            status_counts[status] = count
    for active_status in KNOWLEDGE_ACTIVE_ITEM_STATUSES:
        value = status_counts.pop(active_status, None)
        if isinstance(value, int) and value > 0:
            moved_active_count += value
    if moved_active_count > 0:
        current_value = status_counts.get(terminal_item_status)
        current_count = current_value if isinstance(current_value, int) else 0
        status_counts[terminal_item_status] = current_count + moved_active_count
    if not status_counts and total_count > 0:
        status_counts[terminal_item_status] = total_count
    return status_counts


def mark_active_items_terminal(
    conn: sqlite3.Connection,
    *,
    knowledge_attachment_id: str,
    terminal_item_status: str,
    error_message: str | None,
) -> None:
    placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ITEM_STATUSES)
    conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachment_items
        SET rag_status = ?,
            error_message = COALESCE(error_message, ?)
        WHERE knowledge_attachment_id = ?
          AND (rag_status IS NULL OR rag_status IN ({placeholders}))
        """,
        (
            terminal_item_status,
            error_message,
            knowledge_attachment_id,
            *KNOWLEDGE_ACTIVE_ITEM_STATUSES,
        ),
    )
