"""SoAI - Pending attachment input rebinding and cancellation [backend/database/repositories/users/conversation_attachment_pending_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.repositories.users.conversation_attachment_unused_marking import (
    ATTACHMENT_UNUSED_ASSIGNMENTS_SQL,
)

__all__ = (
    "sync_cancel_pending_attachment_references",
    "sync_rebind_pending_attachment_references",
)


def sync_rebind_pending_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    source_input_id: str,
    target_input_id: str,
    updated_at_ms: int,
) -> None:
    for table_name in (
        "webui_conversation_attachments",
        "webui_conversation_knowledge_attachments",
    ):
        conn.execute(
            f"""
            UPDATE {table_name}
            SET conversation_input_id = ?, updated_at_ms = ?
            WHERE conv_id = ? AND user_id = ?
              AND conversation_input_id = ? AND state = 'queued'
            """,
            (target_input_id, updated_at_ms, conv_id, user_id, source_input_id),
        )


def sync_cancel_pending_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    conversation_input_id: str,
    updated_at_ms: int,
) -> None:
    conn.execute(
        f"""
        UPDATE webui_conversation_attachments
        {ATTACHMENT_UNUSED_ASSIGNMENTS_SQL}
        WHERE conv_id = ?
          AND user_id = ?
          AND conversation_input_id = ?
          AND state = 'queued'
        """,
        (updated_at_ms, conv_id, user_id, conversation_input_id),
    )
    conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachments
        {ATTACHMENT_UNUSED_ASSIGNMENTS_SQL}
        WHERE conv_id = ?
          AND user_id = ?
          AND conversation_input_id = ?
          AND state = 'queued'
        """,
        (updated_at_ms, conv_id, user_id, conversation_input_id),
    )
