"""SoAI - Knowledge attachment item transactions [backend/database/repositories/users/conversation_attachment_knowledge_items.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
)
from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_PROCESSING_STATES,
)
from core.errors.exceptions import ConflictError, StateError
from core.types.json_value import coerce_json_dict
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_knowledge_counts import (
    terminal_processing_state_from_counts,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
    map_knowledge_attachment_integrity_error,
)
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_add_knowledge_attachment_item",)


def _require_status_counts(value: JSONDict) -> JSONDict:
    status_counts = coerce_json_dict(value.get("status_counts"))
    if status_counts is None:
        raise StateError("Knowledge attachment status_counts is invalid.")
    return status_counts


def _finalize_if_terminal(
    conn: sqlite3.Connection,
    *,
    updated: JSONDict,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    updated_at_ms: int,
) -> JSONDict:
    terminal_state = terminal_processing_state_from_counts(_require_status_counts(updated))
    if terminal_state is None:
        return updated
    next_terminal_state = (
        "cancelled" if updated.get("processing_state") == "cancelling" else terminal_state
    )
    if updated.get("processing_state") == next_terminal_state:
        return updated
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            UPDATE webui_conversation_knowledge_attachments
            SET processing_state = ?,
                finalized_at_ms = COALESCE(finalized_at_ms, ?),
                updated_at_ms = ?,
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ? AND user_id = ? AND id = ?
              AND state = ?
            RETURNING *
            """,
            (
                next_terminal_state,
                updated_at_ms,
                updated_at_ms,
                conv_id,
                user_id,
                knowledge_attachment_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
            ),
        ),
    )
    finalized = format_knowledge_attachment_row(row)
    if finalized is None:
        raise ConflictError("Knowledge attachment changed before terminal item insert.")
    return finalized


def sync_add_knowledge_attachment_item(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    document_id: str | None,
    event_id: int | None,
    item_index: int,
    filename: str,
    file_type: str | None,
    file_size_bytes: int | None,
    rag_status: str,
    operation_type: str,
    error_message: str | None,
    created_at_ms: int,
) -> JSONDict:
    state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_PROCESSING_STATES)
    try:
        cursor = conn.execute(
            f"""
            INSERT OR IGNORE INTO webui_conversation_knowledge_attachment_items (
                knowledge_attachment_id, conv_id, user_id, document_id, event_id, item_index,
                filename, file_type, file_size_bytes, rag_status, operation_type, error_message,
                created_at_ms
            )
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE EXISTS (
                SELECT 1
                FROM webui_conversation_knowledge_attachments
                WHERE conv_id = ?
                  AND user_id = ?
                  AND id = ?
                  AND state = ?
                  AND processing_state IN ({state_placeholders})
            )
            """,
            (
                knowledge_attachment_id,
                conv_id,
                user_id,
                document_id,
                event_id,
                item_index,
                filename,
                file_type,
                file_size_bytes,
                rag_status,
                operation_type,
                error_message,
                created_at_ms,
                conv_id,
                user_id,
                knowledge_attachment_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
                *KNOWLEDGE_ACTIVE_PROCESSING_STATES,
            ),
        )
    except sqlite3.IntegrityError as exception:
        raise map_knowledge_attachment_integrity_error(exception) from exception
    if cursor.rowcount <= 0:
        existing = fetch_knowledge_attachment_by_id(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
        )
        if existing is None:
            raise ConflictError("Knowledge attachment is no longer available.")
        return existing
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            UPDATE webui_conversation_knowledge_attachments
            SET processing_state = CASE
                    WHEN processing_state = 'cancelling' THEN 'cancelling'
                    ELSE 'running'
                END,
                total_count = total_count + 1,
                visible_count = visible_count + 1,
                status_counts_json = json_set(
                    status_counts_json,
                    '$.' || ?,
                    COALESCE(json_extract(status_counts_json, '$.' || ?), 0) + 1
                ),
                updated_at_ms = ?,
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ? AND user_id = ? AND id = ?
              AND state = ?
              AND processing_state IN ({state_placeholders})
            RETURNING *
            """,
            (
                rag_status,
                rag_status,
                created_at_ms,
                conv_id,
                user_id,
                knowledge_attachment_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
                *KNOWLEDGE_ACTIVE_PROCESSING_STATES,
            ),
        ),
    )
    updated = format_knowledge_attachment_row(row)
    if updated is None:
        raise ConflictError("Knowledge attachment changed before item insert summary update.")
    return _finalize_if_terminal(
        conn,
        updated=updated,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        updated_at_ms=created_at_ms,
    )
