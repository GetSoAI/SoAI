"""SoAI - Linked knowledge activation checks [backend/database/repositories/users/conversation_linked_knowledge_activation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
)
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite_numberish
from database.repositories.users.conversation_attachment_knowledge_counts import (
    serialize_status_counts,
)
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)
from database.repositories.users.conversation_linked_knowledge_signature import (
    MISSING_SOURCE_REASON,
    linked_state_signature,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_refresh_linked_knowledge_availability",)


def _target_is_active_linked_attachment(
    conn: sqlite3.Connection,
    *,
    target_knowledge_attachment_id: str,
    active_state_placeholders: str,
) -> bool:
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT 1
            FROM webui_conversation_knowledge_attachments
            WHERE id = ?
              AND source_type = 'linked_knowledge'
              AND state IN ({active_state_placeholders})
            LIMIT 1
            """,
            (target_knowledge_attachment_id, *KNOWLEDGE_ACTIVE_ATTACHMENT_STATES),
        ),
    )
    return row is not None


def sync_refresh_linked_knowledge_availability(
    conn: sqlite3.Connection,
    *,
    target_knowledge_attachment_id: str,
    updated_at_ms: int,
) -> JSONDict | None:
    active_state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ATTACHMENT_STATES)
    if not _target_is_active_linked_attachment(
        conn,
        target_knowledge_attachment_id=target_knowledge_attachment_id,
        active_state_placeholders=active_state_placeholders,
    ):
        return None
    conn.execute(
        """
        UPDATE rag_linked_documents
        SET status = CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM rag_documents document
                    WHERE document.id = rag_linked_documents.source_document_id
                      AND document.conv_id = rag_linked_documents.source_conv_id
                      AND document.user_id = rag_linked_documents.source_user_id
                      AND document.status = 'completed'
                )
                THEN 'active'
                ELSE 'unavailable'
            END,
            unavailable_reason = CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM rag_documents document
                    WHERE document.id = rag_linked_documents.source_document_id
                      AND document.conv_id = rag_linked_documents.source_conv_id
                      AND document.user_id = rag_linked_documents.source_user_id
                      AND document.status = 'completed'
                )
                THEN NULL
                ELSE ?
            END,
            updated_at_ms = ?
        WHERE target_knowledge_attachment_id = ?
        """,
        (MISSING_SOURCE_REASON, updated_at_ms, target_knowledge_attachment_id),
    )
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN status != 'active' THEN 1 ELSE 0 END) AS unavailable_count
            FROM rag_linked_documents
            WHERE target_knowledge_attachment_id = ?
            """,
            (target_knowledge_attachment_id,),
        ),
    )
    if row is None:
        return None
    active_count = coerce_non_negative_int_from_sqlite_numberish(row.get("active_count"))
    unavailable_count = coerce_non_negative_int_from_sqlite_numberish(row.get("unavailable_count"))
    conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachment_items
        SET rag_status = CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM rag_linked_documents link
                    WHERE link.target_knowledge_attachment_id = ?
                      AND link.target_item_id = webui_conversation_knowledge_attachment_items.id
                      AND link.status = 'active'
                )
                THEN 'completed'
                ELSE 'error'
            END,
            error_message = CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM rag_linked_documents link
                    WHERE link.target_knowledge_attachment_id = ?
                      AND link.target_item_id = webui_conversation_knowledge_attachment_items.id
                      AND link.status = 'active'
                )
                THEN NULL
                ELSE ?
            END
        WHERE knowledge_attachment_id = ?
          AND EXISTS (
              SELECT 1
              FROM webui_conversation_knowledge_attachments summary
              WHERE summary.id = webui_conversation_knowledge_attachment_items.knowledge_attachment_id
                AND summary.source_type = 'linked_knowledge'
                AND summary.state IN ({active_state_placeholders})
          )
        """,
        (
            target_knowledge_attachment_id,
            target_knowledge_attachment_id,
            MISSING_SOURCE_REASON,
            target_knowledge_attachment_id,
            *KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
        ),
    )
    child_rows = conn.execute(
        """
        SELECT
            target_item_id,
            status,
            unavailable_reason
        FROM rag_linked_documents
        WHERE target_knowledge_attachment_id = ?
        ORDER BY target_item_id ASC
        """,
        (target_knowledge_attachment_id,),
    ).fetchall()
    child_states: list[JSONDict] = []
    for target_item_id, status, unavailable_reason in child_rows:
        child_states.append(
            {
                "target_item_id": int(target_item_id),
                "status": str(status),
                "unavailable_reason": (
                    str(unavailable_reason) if isinstance(unavailable_reason, str) else None
                ),
            },
        )
    state_signature = linked_state_signature(
        active_count=active_count,
        unavailable_count=unavailable_count,
        child_states=child_states,
    )
    processing_state = "ready" if active_count > 0 else "error"
    status_counts_json = serialize_status_counts(
        {"completed": active_count, "error": unavailable_count},
    )
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachments
        SET processing_state = ?,
            visible_count = ?,
            hidden_count = ?,
            status_counts_json = ?,
            state_signature = ?,
            finalized_at_ms = COALESCE(finalized_at_ms, ?),
            attachment_revision = attachment_revision + 1,
            updated_at_ms = ?
        WHERE id = ?
          AND source_type = 'linked_knowledge'
          AND state IN ({active_state_placeholders})
          AND (
              processing_state IS NOT ?
              OR visible_count IS NOT ?
              OR hidden_count IS NOT ?
              OR status_counts_json IS NOT ?
              OR state_signature IS NOT ?
              OR finalized_at_ms IS NULL
          )
        """,
        (
            processing_state,
            active_count,
            unavailable_count,
            status_counts_json,
            state_signature,
            updated_at_ms,
            updated_at_ms,
            target_knowledge_attachment_id,
            *KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
            processing_state,
            active_count,
            unavailable_count,
            status_counts_json,
            state_signature,
        ),
    )
    if cursor.rowcount <= 0:
        return None
    summary_row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT *
            FROM webui_conversation_knowledge_attachments
            WHERE id = ?
            """,
            (target_knowledge_attachment_id,),
        ),
    )
    return format_knowledge_attachment_row(summary_row)
