"""SoAI - Conversation attachment deletion transactions [backend/database/repositories/users/conversation_attachment_deletion_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.attachment_deletion import AttachmentDeletionPlan
from core.errors.exceptions import ConflictError, StateError
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
from database.repositories.users.conversation_attachment_rows import (
    format_attachment_row,
)
from database.repositories.users.conversation_attachment_unused_marking import (
    sync_mark_reclaimable_attachment_unused_by_id,
    sync_mark_staged_attachment_unused_by_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_finalize_unbound_attachment_deletion",
    "sync_mark_reclaimable_attachment_unused",
    "sync_mark_unbound_attachment_unused",
    "sync_prepare_unbound_attachment_deletion",
)


def _require_unbound_attachment(existing: JSONDict) -> None:
    if existing.get("state") in {"queued", "committed"}:
        raise ConflictError("Attachment is already bound to a message or conversation input.")


def sync_mark_unbound_attachment_unused(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    updated_at_ms: int,
) -> JSONDict | None:
    existing = fetch_file_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if existing is None:
        return None
    _require_unbound_attachment(existing)
    if existing.get("state") == "unused":
        return existing
    row = sync_mark_staged_attachment_unused_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
        updated_at_ms=updated_at_ms,
    )
    formatted = format_attachment_row(row)
    if formatted is None:
        raise StateError("Attachment row missing after delete reservation.")
    return formatted


def sync_mark_reclaimable_attachment_unused(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    updated_at_ms: int,
) -> JSONDict | None:
    existing = fetch_file_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if existing is None:
        return None
    if existing.get("state") == "committed":
        raise ConflictError("Committed attachment cannot be reclaimed by cleanup.")
    if existing.get("state") == "unused":
        return existing
    row = sync_mark_reclaimable_attachment_unused_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
        updated_at_ms=updated_at_ms,
    )
    return format_attachment_row(row)


def sync_prepare_unbound_attachment_deletion(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    attachment_id: str,
) -> AttachmentDeletionPlan | None:
    existing = fetch_file_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if existing is None:
        return None
    _require_unbound_attachment(existing)
    file_id_value = existing.get("file_id")
    if not isinstance(file_id_value, str):
        raise StateError("Attachment file_id is invalid.")
    row = conn.execute(
        """
        SELECT 1
        FROM webui_conversation_attachments
        WHERE file_id = ? AND user_id = ? AND id != ?
        LIMIT 1
        """,
        (file_id_value, user_id, attachment_id),
    ).fetchone()
    if row is not None:
        deleted = conn.execute(
            """
            DELETE FROM webui_conversation_attachments
            WHERE conv_id = ? AND user_id = ? AND id = ?
            """,
            (conv_id, user_id, attachment_id),
        ).rowcount
        if deleted != 1:
            raise StateError("Attachment row missing during shared file deletion.")
    return AttachmentDeletionPlan(
        requires_file_deletion=row is None,
    )


def sync_finalize_unbound_attachment_deletion(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    attachment_id: str,
) -> JSONDict | None:
    existing = fetch_file_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if existing is None:
        return None
    _require_unbound_attachment(existing)
    file_id_value = existing.get("file_id")
    if not isinstance(file_id_value, str):
        raise StateError("Attachment file_id is invalid.")
    deleted = conn.execute(
        """
        DELETE FROM files_catalog
        WHERE id = ?
          AND user_id IS ?
          AND api_key_id IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM webui_conversation_attachments
              WHERE file_id = ? AND user_id = ? AND id != ?
          )
        """,
        (file_id_value, user_id, file_id_value, user_id, attachment_id),
    ).rowcount
    if deleted != 1:
        raise StateError("Attachment file catalog ownership changed during deletion.")
    return existing
