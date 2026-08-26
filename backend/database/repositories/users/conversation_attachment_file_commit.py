"""SoAI - Physical attachment commit transition [backend/database/repositories/users/conversation_attachment_file_commit.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
from database.repositories.users.conversation_attachment_references import (
    FileAttachmentReference,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("commit_file_attachment_reference",)


def _file_commit_write_already_applied(row: JSONDict, *, message_created_at_ms: int) -> bool:
    return (
        row.get("state") == "committed"
        and row.get("conversation_input_id") is None
        and row.get("message_created_at_ms") == message_created_at_ms
        and row.get("parse_state") == "ready"
    )


def _require_file_attachment(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    attachment_id: str,
) -> JSONDict:
    attachment = fetch_file_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if attachment is None:
        raise StateError("File attachment disappeared during commit.")
    return attachment


def commit_file_attachment_reference(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    reference: FileAttachmentReference,
    conversation_input_id: str | None,
    updated_at_ms: int,
) -> JSONDict:
    cursor = conn.execute(
        """
        UPDATE webui_conversation_attachments
        SET state = 'committed',
            conversation_input_id = NULL,
            message_created_at_ms = ?,
            updated_at_ms = ?,
            attachment_revision = attachment_revision + 1
        WHERE conv_id = ?
          AND user_id = ?
          AND id = ?
          AND parse_state = 'ready'
          AND (
              (
                  state = 'staged'
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
            reference.attachment_id,
            conversation_input_id,
            reference.attachment_revision,
            conversation_input_id,
            reference.attachment_revision,
            reference.message_created_at_ms,
            reference.message_created_at_ms,
        ),
    )
    attachment = _require_file_attachment(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=reference.attachment_id,
    )
    if cursor.rowcount == 0 and not _file_commit_write_already_applied(
        attachment,
        message_created_at_ms=reference.message_created_at_ms,
    ):
        raise ConflictError("File attachment commit state changed before message write.")
    return attachment
