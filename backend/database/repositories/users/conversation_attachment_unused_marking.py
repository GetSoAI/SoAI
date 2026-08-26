"""SoAI - Physical attachment unused-state update statements [backend/database/repositories/users/conversation_attachment_unused_marking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.conversation_attachment_draft_reference_sql import (
    attachment_not_referenced_by_draft_sql,
)

__all__ = (
    "ATTACHMENT_UNUSED_ASSIGNMENTS_SQL",
    "sync_mark_reclaimable_attachment_unused_by_id",
    "sync_mark_staged_attachment_unused_by_id",
)

ATTACHMENT_UNUSED_ASSIGNMENTS_SQL = """
SET state = 'unused',
    conversation_input_id = NULL,
    updated_at_ms = ?,
    attachment_revision = attachment_revision + 1
"""


def sync_mark_staged_attachment_unused_by_id(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    updated_at_ms: int,
) -> SQLiteRowDict | None:
    return sync_fetch_one_as_dict(
        conn.execute(
            f"""
            UPDATE webui_conversation_attachments
            {ATTACHMENT_UNUSED_ASSIGNMENTS_SQL}
            WHERE conv_id = ?
              AND user_id = ?
              AND id = ?
              AND state = 'staged'
            RETURNING *
            """,
            (updated_at_ms, conv_id, user_id, attachment_id),
        ),
    )


def sync_mark_reclaimable_attachment_unused_by_id(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    updated_at_ms: int,
) -> SQLiteRowDict | None:
    return sync_fetch_one_as_dict(
        conn.execute(
            f"""
        UPDATE webui_conversation_attachments
        {ATTACHMENT_UNUSED_ASSIGNMENTS_SQL}
        WHERE conv_id = ?
          AND user_id = ?
          AND id = ?
          AND state IN ('staged', 'queued')
          AND (
                conversation_input_id IS NULL
                OR NOT EXISTS (
                    SELECT 1
                    FROM webui_conversation_inputs p
                    WHERE p.input_id = webui_conversation_attachments.conversation_input_id
                      AND p.conv_id = webui_conversation_attachments.conv_id
                      AND p.user_id = webui_conversation_attachments.user_id
                      AND p.state = 'pending'
                )
          )
          {attachment_not_referenced_by_draft_sql("webui_conversation_attachments")}
        RETURNING *
        """,
            (updated_at_ms, conv_id, user_id, attachment_id),
        ),
    )
