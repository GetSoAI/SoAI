"""SoAI - Knowledge attachment terminal finalization transactions [backend/database/repositories/users/conversation_attachment_knowledge_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
    KNOWLEDGE_RECLAIMABLE_ATTACHMENT_STATES,
)
from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_TERMINAL_PROCESSING_STATES,
)
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
)
from database.repositories.users.conversation_attachment_knowledge_activity import (
    sync_knowledge_attachment_has_active_items,
)
from database.repositories.users.conversation_attachment_knowledge_counts import (
    serialize_status_counts,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_summary_updates import (
    sync_update_active_knowledge_attachment_terminal_status,
)
from database.repositories.users.conversation_attachment_knowledge_terminal_counts import (
    mark_active_items_terminal,
    terminal_status_counts,
)
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)

KNOWLEDGE_ATTACHMENT_FIELD_LABEL = "Knowledge attachment field"

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_finalize_knowledge_attachment_by_id",
    "sync_finalize_knowledge_attachment_task",
)


def _fetch_summary_by_task_id(
    conn: sqlite3.Connection,
    *,
    task_id: str,
) -> JSONDict | None:
    state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_ATTACHMENT_STATES)
    row = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT *
            FROM webui_conversation_knowledge_attachments
            WHERE task_id = ?
              AND state IN ({state_placeholders})
            ORDER BY created_at_ms DESC
            LIMIT 1
            """,
            (task_id, *KNOWLEDGE_ACTIVE_ATTACHMENT_STATES),
        ),
    )
    return format_knowledge_attachment_row(row)


def _update_terminal_summary(
    conn: sqlite3.Connection,
    *,
    summary: JSONDict,
    processing_state: str,
    terminal_item_status: str,
    error_message: str | None,
    state: str | None,
) -> JSONDict | None:
    knowledge_attachment_id = require_sqlite_row_non_empty_str(
        summary,
        "knowledge_attachment_id",
        label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
    )
    total_count = require_sqlite_row_int(
        summary,
        "total_count",
        label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
    )
    now = epoch_ms()
    status_counts = terminal_status_counts(
        conn,
        knowledge_attachment_id=knowledge_attachment_id,
        terminal_item_status=terminal_item_status,
        total_count=total_count,
    )
    mark_active_items_terminal(
        conn,
        knowledge_attachment_id=knowledge_attachment_id,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
    )
    if state is None:
        updated_terminal = sync_update_active_knowledge_attachment_terminal_status(
            conn,
            processing_state=processing_state,
            status_counts_json=serialize_status_counts(status_counts),
            updated_at_ms=now,
            finalized_at_ms=now,
            knowledge_attachment_id=knowledge_attachment_id,
            active_states=KNOWLEDGE_ACTIVE_ATTACHMENT_STATES,
        )
    else:
        state_placeholders = ",".join("?" for _ in KNOWLEDGE_RECLAIMABLE_ATTACHMENT_STATES)
        cursor = conn.execute(
            f"""
            UPDATE webui_conversation_knowledge_attachments
            SET state = ?,
                conversation_input_id = NULL,
                message_created_at_ms = NULL,
                processing_state = ?,
                status_counts_json = ?,
                updated_at_ms = ?,
                finalized_at_ms = COALESCE(finalized_at_ms, ?),
                attachment_revision = attachment_revision + 1
            WHERE id = ?
              AND state IN ({state_placeholders})
            """,
            (
                state,
                processing_state,
                serialize_status_counts(status_counts),
                now,
                now,
                knowledge_attachment_id,
                *KNOWLEDGE_RECLAIMABLE_ATTACHMENT_STATES,
            ),
        )
        updated_terminal = cursor.rowcount == 1
    if not updated_terminal:
        raise StateError("Knowledge attachment changed during terminal finalization.")
    updated = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=require_sqlite_row_non_empty_str(
            summary,
            "conv_id",
            label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
        ),
        user_id=require_sqlite_row_int(summary, "user_id", label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL),
        knowledge_attachment_id=knowledge_attachment_id,
    )
    return updated


def _finalize_summary(
    conn: sqlite3.Connection,
    *,
    summary: JSONDict,
    processing_state: str,
    terminal_item_status: str,
    error_message: str | None,
    state: str | None,
) -> JSONDict | None:
    current_processing_state = summary.get("processing_state")
    current_state = summary.get("state")
    allowed_states = (
        KNOWLEDGE_ACTIVE_ATTACHMENT_STATES
        if state is None
        else KNOWLEDGE_RECLAIMABLE_ATTACHMENT_STATES
    )
    if current_state not in allowed_states:
        return None
    finalized_at_ms = summary.get("finalized_at_ms")
    if current_processing_state in KNOWLEDGE_TERMINAL_PROCESSING_STATES and (
        state is None or current_state == state
    ):
        has_active_items = sync_knowledge_attachment_has_active_items(
            conn,
            conv_id=require_sqlite_row_non_empty_str(
                summary,
                "conv_id",
                label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
            ),
            user_id=require_sqlite_row_int(
                summary,
                "user_id",
                label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
            ),
            knowledge_attachment_id=require_sqlite_row_non_empty_str(
                summary,
                "knowledge_attachment_id",
                label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
            ),
        )
        if (
            not has_active_items
            and isinstance(finalized_at_ms, int)
            and not isinstance(finalized_at_ms, bool)
        ):
            return summary
    return _update_terminal_summary(
        conn,
        summary=summary,
        processing_state=processing_state,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
        state=state,
    )


def sync_finalize_knowledge_attachment_by_id(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    processing_state: str,
    terminal_item_status: str,
    error_message: str | None,
    state: str | None,
) -> JSONDict | None:
    summary = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if summary is None:
        return None
    return _finalize_summary(
        conn,
        summary=summary,
        processing_state=processing_state,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
        state=state,
    )


def sync_finalize_knowledge_attachment_task(
    conn: sqlite3.Connection,
    task_id: str,
    processing_state: str,
    terminal_item_status: str,
    error_message: str | None,
) -> JSONDict | None:
    summary = _fetch_summary_by_task_id(conn, task_id=task_id)
    if summary is None:
        return None
    return _finalize_summary(
        conn,
        summary=summary,
        processing_state=processing_state,
        terminal_item_status=terminal_item_status,
        error_message=error_message,
        state=None,
    )
