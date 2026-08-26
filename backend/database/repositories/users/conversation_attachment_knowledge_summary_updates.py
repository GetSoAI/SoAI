"""SoAI - Knowledge attachment summary update statements [backend/database/repositories/users/conversation_attachment_knowledge_summary_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Collection

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
    KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
)
from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_PROCESSING_STATES,
)

__all__ = (
    "sync_update_cancellable_knowledge_attachment_summary_status",
    "sync_update_active_knowledge_attachment_terminal_status",
)


def sync_update_cancellable_knowledge_attachment_summary_status(
    conn: sqlite3.Connection,
    *,
    processing_state: str,
    status_counts_json: str,
    updated_at_ms: int,
    finalized_at_ms: int | None,
    knowledge_attachment_id: str,
) -> bool:
    state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_PROCESSING_STATES)
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachments
        SET processing_state = ?,
            status_counts_json = ?,
            updated_at_ms = ?,
            finalized_at_ms = COALESCE(finalized_at_ms, ?),
            attachment_revision = attachment_revision + 1
        WHERE id = ?
          AND (
              (state = ? AND processing_state IN ({state_placeholders}))
              OR (state = ? AND processing_state = 'cancelling')
          )
        """,
        (
            processing_state,
            status_counts_json,
            updated_at_ms,
            finalized_at_ms,
            knowledge_attachment_id,
            KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
            *KNOWLEDGE_ACTIVE_PROCESSING_STATES,
            KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
        ),
    )
    return cursor.rowcount == 1


def sync_update_active_knowledge_attachment_terminal_status(
    conn: sqlite3.Connection,
    *,
    processing_state: str,
    status_counts_json: str,
    updated_at_ms: int,
    finalized_at_ms: int,
    knowledge_attachment_id: str,
    active_states: Collection[str],
) -> bool:
    state_placeholders = ",".join("?" for _ in active_states)
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachments
        SET processing_state = ?,
            status_counts_json = ?,
            updated_at_ms = ?,
            finalized_at_ms = COALESCE(finalized_at_ms, ?),
            attachment_revision = attachment_revision + 1
        WHERE id = ?
          AND state IN ({state_placeholders})
        """,
        (
            processing_state,
            status_counts_json,
            updated_at_ms,
            finalized_at_ms,
            knowledge_attachment_id,
            *active_states,
        ),
    )
    return cursor.rowcount == 1
