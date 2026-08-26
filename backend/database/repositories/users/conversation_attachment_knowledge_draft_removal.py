"""SoAI - Draft knowledge attachment removal transaction [backend/database/repositories/users/conversation_attachment_knowledge_draft_removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
    KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
)
from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_PROCESSING_STATES,
)
from core.errors.exceptions import ConflictError, StateError
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_knowledge_activity import (
    sync_knowledge_attachment_has_active_items,
)
from database.repositories.users.conversation_attachment_knowledge_counts import (
    serialize_status_counts,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_terminal_counts import (
    mark_active_items_terminal,
    terminal_status_counts,
)
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_remove_draft_knowledge_attachment",)


def sync_remove_draft_knowledge_attachment(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict:
    existing = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if existing is None:
        raise ConflictError("Knowledge attachment is no longer available.")
    if existing.get("state") != KNOWLEDGE_DRAFT_ATTACHMENT_STATE:
        raise ConflictError("Knowledge attachment is no longer in the draft.")
    processing_state = existing.get("processing_state")
    if processing_state in KNOWLEDGE_ACTIVE_PROCESSING_STATES:
        task_id = existing.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            if not sync_knowledge_attachment_has_active_items(
                conn,
                conv_id=conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
            ):
                return _mark_active_draft_without_task_unused(
                    conn,
                    conv_id=conv_id,
                    user_id=user_id,
                    knowledge_attachment_id=knowledge_attachment_id,
                    total_count=_resolve_total_count(existing),
                )
        return _mark_draft_attachment_unused(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
            processing_state="cancelling",
            finalized_at_ms=None,
        )
    return _mark_draft_attachment_unused(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        processing_state=processing_state if isinstance(processing_state, str) else "cancelled",
        finalized_at_ms=_resolve_finalized_at_ms(existing),
    )


def _resolve_finalized_at_ms(summary: JSONDict) -> int | None:
    finalized_at_ms = summary.get("finalized_at_ms")
    return finalized_at_ms if is_strict_int(finalized_at_ms) else None


def _resolve_total_count(summary: JSONDict) -> int:
    total_count = summary.get("total_count")
    if not is_strict_int(total_count) or total_count < 0:
        raise StateError("Knowledge attachment total_count is invalid.")
    return total_count


def _mark_draft_attachment_unused(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    processing_state: str,
    finalized_at_ms: int | None,
) -> JSONDict:
    now = epoch_ms()
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            UPDATE webui_conversation_knowledge_attachments
            SET state = ?,
                conversation_input_id = NULL,
                message_created_at_ms = NULL,
                processing_state = ?,
                updated_at_ms = ?,
                finalized_at_ms = COALESCE(?, finalized_at_ms),
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ? AND user_id = ? AND id = ? AND state = ?
            RETURNING *
            """,
            (
                KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
                processing_state,
                now,
                finalized_at_ms,
                conv_id,
                user_id,
                knowledge_attachment_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
            ),
        ),
    )
    formatted = format_knowledge_attachment_row(row)
    if formatted is None:
        raise StateError("Knowledge attachment row missing after draft removal.")
    return formatted


def _mark_active_draft_without_task_unused(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    total_count: int,
) -> JSONDict:
    now = epoch_ms()
    mark_active_items_terminal(
        conn,
        knowledge_attachment_id=knowledge_attachment_id,
        terminal_item_status="cancelled",
        error_message="Removed by user",
    )
    status_counts = terminal_status_counts(
        conn,
        knowledge_attachment_id=knowledge_attachment_id,
        terminal_item_status="cancelled",
        total_count=total_count,
    )
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            UPDATE webui_conversation_knowledge_attachments
            SET state = ?,
                conversation_input_id = NULL,
                message_created_at_ms = NULL,
                processing_state = 'cancelled',
                status_counts_json = ?,
                updated_at_ms = ?,
                finalized_at_ms = COALESCE(finalized_at_ms, ?),
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ? AND user_id = ? AND id = ? AND state = ?
            RETURNING *
            """,
            (
                KNOWLEDGE_UNUSED_ATTACHMENT_STATE,
                serialize_status_counts(status_counts),
                now,
                now,
                conv_id,
                user_id,
                knowledge_attachment_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
            ),
        ),
    )
    formatted = format_knowledge_attachment_row(row)
    if formatted is None:
        raise StateError("Knowledge attachment row missing after active draft removal.")
    return formatted
