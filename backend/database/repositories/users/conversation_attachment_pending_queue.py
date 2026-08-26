"""SoAI - Conversation input attachment queue canonicalization [backend/database/repositories/users/conversation_attachment_pending_queue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.attachments.attachment_content_parts import (
    content_part_from_file_attachment,
    content_part_from_knowledge_summary,
)
from database.repositories.users.conversation_attachment_queue_transitions import (
    queue_file_attachment_reference,
    queue_knowledge_attachment_reference,
)
from database.repositories.users.conversation_attachment_reference_validation import (
    sync_validate_nonqueued_attachment_references,
)
from database.repositories.users.conversation_attachment_references import (
    ConversationAttachmentReferences,
    extract_content_attachment_references,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_queue_pending_attachment_references",)


def _has_references(references: ConversationAttachmentReferences) -> bool:
    return bool(references.files or references.knowledge)


def _queue_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    conversation_input_id: str,
    references: ConversationAttachmentReferences,
    updated_at_ms: int,
) -> tuple[dict[str, JSONDict], dict[str, JSONDict]]:
    file_parts: dict[str, JSONDict] = {}
    knowledge_parts: dict[str, JSONDict] = {}
    for file_reference in references.files:
        attachment = queue_file_attachment_reference(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            conversation_input_id=conversation_input_id,
            reference=file_reference,
            updated_at_ms=updated_at_ms,
        )
        file_parts[file_reference.attachment_id] = content_part_from_file_attachment(attachment)
    for knowledge_reference in references.knowledge:
        summary = queue_knowledge_attachment_reference(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            conversation_input_id=conversation_input_id,
            reference=knowledge_reference,
            updated_at_ms=updated_at_ms,
        )
        knowledge_parts[knowledge_reference.knowledge_attachment_id] = (
            content_part_from_knowledge_summary(summary)
        )
    return file_parts, knowledge_parts


def _replace_queued_attachment_content(
    attachment_content: list[JSONValue],
    *,
    file_parts: dict[str, JSONDict],
    knowledge_parts: dict[str, JSONDict],
) -> list[JSONValue]:
    if not file_parts and not knowledge_parts:
        return list(attachment_content)
    canonical_content: list[JSONValue] = []
    for entry in attachment_content:
        if isinstance(entry, dict) and entry.get("type") == "soai_file":
            attachment_id = entry.get("attachment_id")
            if isinstance(attachment_id, str) and attachment_id in file_parts:
                canonical_content.append(file_parts[attachment_id])
                continue
        if isinstance(entry, dict) and entry.get("type") == "soai_knowledge":
            knowledge_attachment_id = entry.get("knowledge_attachment_id")
            if (
                isinstance(knowledge_attachment_id, str)
                and knowledge_attachment_id in knowledge_parts
            ):
                canonical_content.append(knowledge_parts[knowledge_attachment_id])
                continue
        canonical_content.append(entry)
    return canonical_content


def sync_queue_pending_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    attachment_content: list[JSONValue],
    conversation_input_id: str,
    updated_at_ms: int,
    storage_root: str | None = None,
) -> list[JSONValue]:
    references = extract_content_attachment_references(
        attachment_content,
        message_created_at_ms=updated_at_ms,
    )
    if not _has_references(references):
        return list(attachment_content)
    sync_validate_nonqueued_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        storage_root=storage_root,
    )
    file_parts, knowledge_parts = _queue_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        conversation_input_id=conversation_input_id,
        references=references,
        updated_at_ms=updated_at_ms,
    )
    return _replace_queued_attachment_content(
        attachment_content,
        file_parts=file_parts,
        knowledge_parts=knowledge_parts,
    )
