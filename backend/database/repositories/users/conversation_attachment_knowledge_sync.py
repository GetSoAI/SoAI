"""SoAI - Knowledge attachment transactions [backend/database/repositories/users/conversation_attachment_knowledge_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.attachment_content_parts import (
    content_part_from_knowledge_summary,
)
from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
)
from core.attachments.knowledge_attachment_statuses import (
    KNOWLEDGE_ACTIVE_PROCESSING_STATES,
    KNOWLEDGE_TERMINAL_PROCESSING_STATES,
)
from core.errors.exceptions import ConflictError, StateError
from core.timing.epoch import epoch_ms
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_row_scalars import require_sqlite_row_int
from database.repositories.users.conversation_attachment_knowledge_activity import (
    sync_knowledge_attachment_has_active_items,
)
from database.repositories.users.conversation_attachment_knowledge_counts import (
    serialize_status_counts,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_readiness import (
    knowledge_attachment_has_completed_items,
    knowledge_attachment_has_finalized_timestamp,
    knowledge_attachment_processing_state_ready,
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
    "sync_cancel_knowledge_attachment",
    "sync_claim_knowledge_attachments",
)


def _require_unique_claim_selections(selections: list[tuple[str, int]]) -> None:
    if not selections:
        raise ConflictError("Knowledge attachment selection is required.")
    selected_ids: set[str] = set()
    for knowledge_attachment_id, expected_revision in selections:
        if not isinstance(knowledge_attachment_id, str) or not knowledge_attachment_id.strip():
            raise ConflictError("Knowledge attachment selection is invalid.")
        if (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise ConflictError("Knowledge attachment revision is invalid.")
        if knowledge_attachment_id in selected_ids:
            raise ConflictError("Duplicate knowledge attachment reference.")
        selected_ids.add(knowledge_attachment_id)


def _require_selected_row(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    expected_revision: int,
) -> JSONDict:
    summary = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if summary is None:
        raise ConflictError("Knowledge attachment is no longer available.")
    if summary.get("state") != KNOWLEDGE_DRAFT_ATTACHMENT_STATE:
        raise ConflictError("Knowledge attachment is no longer in the draft.")
    if summary.get("attachment_revision") != expected_revision:
        raise ConflictError("Knowledge attachment changed before claim.")
    expires_at_ms = require_sqlite_row_int(
        summary,
        "expires_at_ms",
        label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
    )
    if expires_at_ms <= epoch_ms():
        raise ConflictError("Knowledge attachment expired before claim.")
    if not knowledge_attachment_processing_state_ready(summary.get("processing_state")):
        raise ConflictError("Knowledge attachment is not ready to claim.")
    if not knowledge_attachment_has_completed_items(summary):
        raise ConflictError("Knowledge attachment has no completed items.")
    if not knowledge_attachment_has_finalized_timestamp(summary):
        raise StateError("Knowledge attachment finalized timestamp is invalid.")
    if sync_knowledge_attachment_has_active_items(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    ):
        raise ConflictError("Knowledge attachment still has active items.")
    return summary


def sync_claim_knowledge_attachments(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    selections: list[tuple[str, int]],
) -> list[JSONDict]:
    _require_unique_claim_selections(selections)
    claimed_parts: list[JSONDict] = []
    for knowledge_attachment_id, expected_revision in selections:
        summary = _require_selected_row(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
            expected_revision=expected_revision,
        )
        claimed_parts.append(content_part_from_knowledge_summary(summary))
    return claimed_parts


def _cancel_without_task(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    total_count: int,
    now: int,
) -> JSONDict:
    mark_active_items_terminal(
        conn,
        knowledge_attachment_id=knowledge_attachment_id,
        terminal_item_status="cancelled",
        error_message="Cancelled by user",
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
            SET processing_state = 'cancelled',
                status_counts_json = ?,
                finalized_at_ms = COALESCE(finalized_at_ms, ?),
                updated_at_ms = ?,
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ? AND user_id = ? AND id = ?
              AND state = ?
            RETURNING *
            """,
            (
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
        raise ConflictError("Knowledge attachment changed before no-task cancel.")
    return formatted


def sync_cancel_knowledge_attachment(
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
    processing_state = existing.get("processing_state")
    if processing_state in KNOWLEDGE_TERMINAL_PROCESSING_STATES:
        return existing
    if existing.get("state") != KNOWLEDGE_DRAFT_ATTACHMENT_STATE:
        raise ConflictError("Knowledge attachment is no longer cancellable.")
    task_id = existing.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        if not sync_knowledge_attachment_has_active_items(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
        ):
            return _cancel_without_task(
                conn,
                conv_id=conv_id,
                user_id=user_id,
                knowledge_attachment_id=knowledge_attachment_id,
                total_count=require_sqlite_row_int(
                    existing,
                    "total_count",
                    label=KNOWLEDGE_ATTACHMENT_FIELD_LABEL,
                ),
                now=epoch_ms(),
            )
    now = epoch_ms()
    state_placeholders = ",".join("?" for _ in KNOWLEDGE_ACTIVE_PROCESSING_STATES)
    updated_rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"""
            UPDATE webui_conversation_knowledge_attachments
            SET processing_state = 'cancelling',
                updated_at_ms = ?,
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ?
              AND user_id = ?
              AND id = ?
              AND state = ?
              AND processing_state IN ({state_placeholders})
            RETURNING *
            """,
            (
                now,
                conv_id,
                user_id,
                knowledge_attachment_id,
                KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
                *KNOWLEDGE_ACTIVE_PROCESSING_STATES,
            ),
        ),
    )
    if len(updated_rows) > 1:
        raise StateError("Knowledge attachment cancel updated multiple rows.")
    if not updated_rows:
        latest = fetch_knowledge_attachment_by_id(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
        )
        if latest is None:
            raise ConflictError("Knowledge attachment is no longer available.")
        return latest
    formatted = format_knowledge_attachment_row(updated_rows[0])
    if formatted is None:
        raise StateError("Knowledge attachment row missing after cancel.")
    return formatted
