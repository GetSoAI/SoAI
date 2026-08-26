"""SoAI - Knowledge attachment commit transition [backend/database/repositories/users/conversation_attachment_knowledge_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from database.repositories.users.conversation_attachment_knowledge_activity import (
    sync_knowledge_attachment_has_active_items,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_readiness import (
    knowledge_attachment_has_completed_items,
    knowledge_attachment_has_finalized_timestamp,
    knowledge_attachment_processing_state_ready,
    knowledge_attachment_ready_for_reference_params,
    knowledge_attachment_ready_for_reference_sql,
)
from database.repositories.users.conversation_attachment_references import (
    KnowledgeAttachmentReference,
)
from database.repositories.users.conversation_linked_knowledge_activation import (
    sync_refresh_linked_knowledge_availability,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("commit_knowledge_attachment_reference",)


def _commit_write_already_applied(row: JSONDict, *, message_created_at_ms: int) -> bool:
    return (
        row.get("state") == "committed"
        and row.get("conversation_input_id") is None
        and row.get("message_created_at_ms") == message_created_at_ms
    )


def _fetch_knowledge_attachment(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict:
    summary = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if summary is None:
        raise StateError("Knowledge attachment disappeared during commit.")
    return summary


def _knowledge_commit_write_already_applied(
    conn: sqlite3.Connection,
    row: JSONDict,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    message_created_at_ms: int,
) -> bool:
    return (
        _commit_write_already_applied(row, message_created_at_ms=message_created_at_ms)
        and knowledge_attachment_processing_state_ready(row.get("processing_state"))
        and knowledge_attachment_has_completed_items(row)
        and knowledge_attachment_has_finalized_timestamp(row)
        and not sync_knowledge_attachment_has_active_items(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_attachment_id,
        )
    )


def commit_knowledge_attachment_reference(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    reference: KnowledgeAttachmentReference,
    conversation_input_id: str | None,
    updated_at_ms: int,
) -> JSONDict:
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachments
        SET state = 'committed',
            conversation_input_id = NULL,
            message_created_at_ms = ?,
            updated_at_ms = ?,
            attachment_revision = attachment_revision + 1
        WHERE conv_id = ?
          AND user_id = ?
          AND id = ?
          {knowledge_attachment_ready_for_reference_sql()}
          AND (
              (
                  state = 'draft'
                  AND conversation_input_id IS NULL
                  AND ? IS NULL
                  AND attachment_revision = ?
              )
              OR (
                  state = 'queued'
                  AND conversation_input_id = ?
                  AND attachment_revision = ?
              )
              OR (
                  state = 'committed'
                  AND conversation_input_id IS NULL
                  AND message_created_at_ms IS ?
              )
          )
          AND (
              state != 'committed'
              OR conversation_input_id IS NOT NULL
              OR message_created_at_ms IS NOT ?
          )
        """,
        (
            reference.message_created_at_ms,
            updated_at_ms,
            conv_id,
            user_id,
            reference.knowledge_attachment_id,
            *knowledge_attachment_ready_for_reference_params(),
            conversation_input_id,
            reference.attachment_revision,
            conversation_input_id,
            reference.attachment_revision,
            reference.message_created_at_ms,
            reference.message_created_at_ms,
        ),
    )
    summary = _fetch_knowledge_attachment(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=reference.knowledge_attachment_id,
    )
    if cursor.rowcount == 0 and not _knowledge_commit_write_already_applied(
        conn,
        summary,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=reference.knowledge_attachment_id,
        message_created_at_ms=reference.message_created_at_ms,
    ):
        raise ConflictError("Knowledge attachment commit state changed before message write.")
    if summary.get("source_type") != "linked_knowledge" or cursor.rowcount == 0:
        return summary
    sync_refresh_linked_knowledge_availability(
        conn,
        target_knowledge_attachment_id=reference.knowledge_attachment_id,
        updated_at_ms=updated_at_ms,
    )
    return _fetch_knowledge_attachment(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=reference.knowledge_attachment_id,
    )
