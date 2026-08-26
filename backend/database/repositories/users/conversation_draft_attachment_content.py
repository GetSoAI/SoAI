"""SoAI - Conversation draft attachment content validation [backend/database/repositories/users/conversation_draft_attachment_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.attachment_content_parts import content_part_from_file_attachment
from core.errors.exceptions import ConflictError, StateError, ValidationError
from database.repositories.users.conversation_attachment_file_availability import (
    sync_require_attachment_file_available,
)
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
from database.repositories.users.conversation_attachment_reference_validation import (
    sync_validate_nonqueued_attachment_references,
)
from database.repositories.users.conversation_attachment_references import (
    ConversationAttachmentReferences,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "canonicalize_conversation_draft_attachment_content",
    "require_non_empty_conversation_draft",
)


def require_non_empty_conversation_draft(
    text: str,
    attachment_content: list[JSONValue],
) -> None:
    if text == "" and not attachment_content:
        raise ValidationError("Conversation draft requires text or attachment_content.")


def _require_draft_file_references(references: ConversationAttachmentReferences) -> None:
    if references.knowledge:
        raise ValidationError("Conversation drafts do not support knowledge attachments.")
    attachment_ids: set[str] = set()
    for file_reference in references.files:
        if file_reference.attachment_id in attachment_ids:
            raise ConflictError("Duplicate file attachment reference.")
        attachment_ids.add(file_reference.attachment_id)


def _require_draft_file_attachment(row: JSONDict) -> None:
    if row.get("state") != "staged":
        raise ConflictError("Draft file attachment must be staged.")
    if row.get("parse_state") != "ready":
        raise ConflictError("Draft file attachment must be ready.")
    if row.get("conversation_input_id") is not None:
        raise ConflictError("Draft file attachment is reserved by a conversation input.")


def _validate_draft_file_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    references: ConversationAttachmentReferences,
    storage_root: str | None,
) -> dict[str, JSONDict]:
    if not references.files:
        return {}
    _require_draft_file_references(references)
    sync_validate_nonqueued_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        storage_root=storage_root,
    )
    attachments: dict[str, JSONDict] = {}
    for file_reference in references.files:
        attachment = fetch_file_attachment_by_id(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            attachment_id=file_reference.attachment_id,
        )
        if attachment is None:
            raise ConflictError("Draft file attachment is not available.")
        _require_draft_file_attachment(attachment)
        sync_require_attachment_file_available(
            conn,
            file_id=file_reference.file_id,
            user_id=user_id,
            size_bytes=file_reference.size_bytes,
            storage_root=storage_root,
        )
        attachments[file_reference.attachment_id] = attachment
    return attachments


def canonicalize_conversation_draft_attachment_content(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    entries: list[JSONValue],
    references: ConversationAttachmentReferences,
    storage_root: str | None,
) -> list[JSONValue]:
    file_attachments = _validate_draft_file_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        storage_root=storage_root,
    )
    canonical_entries: list[JSONValue] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise StateError("Validated draft entry is not an object.")
        if entry.get("type") == "soai_file":
            attachment_id = entry.get("attachment_id")
            if not isinstance(attachment_id, str) or attachment_id not in file_attachments:
                raise ConflictError("Draft file attachment is not available.")
            canonical_entries.append(
                content_part_from_file_attachment(file_attachments[attachment_id]),
            )
            continue
        canonical_entries.append(dict(entry))
    return canonical_entries
