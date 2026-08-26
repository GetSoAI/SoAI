"""SoAI - Knowledge attachment status update transactions [backend/database/repositories/users/conversation_attachment_knowledge_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
    KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
)
from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_ITEM_STATUSES,
    KNOWLEDGE_ACTIVE_PROCESSING_STATES,
    KNOWLEDGE_TERMINAL_ITEM_STATUSES,
    KNOWLEDGE_TERMINAL_PROCESSING_STATES,
)
from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
)
from database.repositories.users.conversation_attachment_knowledge_counts import (
    apply_status_count_transition,
    serialize_status_counts,
    terminal_processing_state_from_counts,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_summary_updates import (
    sync_update_cancellable_knowledge_attachment_summary_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_update_knowledge_attachment_item_status_for_document",)

KNOWLEDGE_ATTACHMENT_FIELD_LABEL = "Knowledge attachment field"


def _fetch_item_for_document(
    conn: sqlite3.Connection,
    *,
    document_id: str,
) -> SQLiteRowDict | None:
    state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_PROCESSING_STATES)
    return sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT item.*, summary.status_counts_json, summary.processing_state
            FROM webui_conversation_knowledge_attachment_items item
            JOIN webui_conversation_knowledge_attachments summary
              ON summary.id = item.knowledge_attachment_id
            WHERE item.document_id = ?
              AND summary.source_type != 'linked_knowledge'
              AND (
                  summary.state = ?
                  OR (
                      summary.state = ?
                      AND summary.processing_state = 'cancelling'
                  )
              )
              AND summary.processing_state IN ({state_placeholders})
            ORDER BY item.id DESC
            LIMIT 1
            """,
            (
                document_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
                KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
                *KNOWLEDGE_ACTIVE_PROCESSING_STATES,
            ),
        ),
    )


def _normalize_next_processing_state(
    *,
    previous_processing_state: str,
    status_counts: JSONDict,
) -> str:
    terminal_state = terminal_processing_state_from_counts(status_counts)
    if terminal_state is None:
        if previous_processing_state == "cancelling":
            return "cancelling"
        return "running"
    if previous_processing_state == "cancelling":
        return "cancelled"
    return terminal_state


def _update_active_draft_item_status(
    conn: sqlite3.Connection,
    *,
    item_id: int,
    previous_status: str | None,
    rag_status: str,
    error_message: str | None,
) -> bool:
    item_status_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ITEM_STATUSES)
    state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_PROCESSING_STATES)
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            UPDATE webui_conversation_knowledge_attachment_items
            SET rag_status = ?,
                error_message = COALESCE(?, error_message)
            WHERE id = ?
              AND ((? IS NULL AND rag_status IS NULL) OR rag_status = ?)
              AND (rag_status IS NULL OR rag_status IN ({item_status_placeholders}))
              AND EXISTS (
                  SELECT 1
                  FROM webui_conversation_knowledge_attachments summary
                  WHERE summary.id = webui_conversation_knowledge_attachment_items.knowledge_attachment_id
                    AND summary.source_type != 'linked_knowledge'
                    AND (
                        summary.state = ?
                        OR (
                            summary.state = ?
                            AND summary.processing_state = 'cancelling'
                        )
                    )
                    AND summary.processing_state IN ({state_placeholders})
              )
            RETURNING id
            """,
            (
                rag_status,
                error_message,
                item_id,
                previous_status,
                previous_status,
                *KNOWLEDGE_ACTIVE_ITEM_STATUSES,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
                KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
                *KNOWLEDGE_ACTIVE_PROCESSING_STATES,
            ),
        ),
    )
    return row is not None


def sync_update_knowledge_attachment_item_status_for_document(
    conn: sqlite3.Connection,
    document_id: str,
    rag_status: str,
    error_message: str | None,
    updated_at_ms: int,
) -> JSONDict | None:
    item = _fetch_item_for_document(conn, document_id=document_id)
    if item is None:
        return None
    previous_status = item.get("rag_status")
    previous_status_text = previous_status if isinstance(previous_status, str) else None
    if previous_status_text in KNOWLEDGE_TERMINAL_ITEM_STATUSES:
        return None
    if previous_status_text == rag_status and error_message is None:
        return None
    status_counts_raw = item.get("status_counts_json")
    if not isinstance(status_counts_raw, str):
        raise StateError("Knowledge attachment status_counts_json is invalid.")
    status_counts = (
        parse_json_dict(status_counts_raw, field="status_counts_json")
        if previous_status_text == rag_status
        else apply_status_count_transition(
            status_counts_raw,
            previous_status=previous_status_text,
            next_status=rag_status,
        )
    )
    previous_processing_state_value = item.get("processing_state")
    previous_processing_state = (
        previous_processing_state_value
        if isinstance(previous_processing_state_value, str)
        else "running"
    )
    next_processing_state = _normalize_next_processing_state(
        previous_processing_state=previous_processing_state,
        status_counts=status_counts,
    )
    finalized_at_ms = (
        updated_at_ms if next_processing_state in KNOWLEDGE_TERMINAL_PROCESSING_STATES else None
    )
    if not _update_active_draft_item_status(
        conn,
        item_id=require_sqlite_row_int(item, "id", label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL),
        previous_status=previous_status_text,
        rag_status=rag_status,
        error_message=error_message,
    ):
        return None
    if not sync_update_cancellable_knowledge_attachment_summary_status(
        conn,
        processing_state=next_processing_state,
        status_counts_json=serialize_status_counts(status_counts),
        updated_at_ms=updated_at_ms,
        finalized_at_ms=finalized_at_ms,
        knowledge_attachment_id=require_sqlite_row_non_empty_str(
            item,
            "knowledge_attachment_id",
            label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
        ),
    ):
        raise StateError("Knowledge attachment summary changed after item status update.")
    return fetch_knowledge_attachment_by_id(
        conn,
        conv_id=require_sqlite_row_non_empty_str(
            item,
            "conv_id",
            label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
        ),
        user_id=require_sqlite_row_int(item, "user_id", label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL),
        knowledge_attachment_id=require_sqlite_row_non_empty_str(
            item,
            "knowledge_attachment_id",
            label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
        ),
    )
