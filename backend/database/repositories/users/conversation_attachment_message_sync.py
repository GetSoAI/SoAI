"""SoAI - Conversation attachment message lifecycle synchronization [backend/database/repositories/users/conversation_attachment_message_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.repositories.users.conversation_attachment_commit_sync import (
    sync_commit_attachment_references,
    sync_replace_committed_attachment_parts,
)
from database.repositories.users.conversation_attachment_reference_validation import (
    sync_validate_attachment_references,
)
from database.repositories.users.conversation_attachment_references import (
    extract_message_attachment_references,
)
from database.repositories.users.conversation_attachment_unreference_sync import (
    sync_mark_unreferenced_conversation_attachments_unused,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_apply_append_attachment_references",
    "sync_apply_overwrite_attachment_references",
)


def sync_apply_append_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    messages: list[JSONDict],
    updated_at_ms: int,
    conversation_input_id: str | None = None,
    storage_root: str | None = None,
) -> tuple[list[JSONDict], list[JSONDict]]:
    references = extract_message_attachment_references(messages)
    sync_validate_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        conversation_input_id=conversation_input_id,
        storage_root=storage_root,
    )
    committed = sync_commit_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        conversation_input_id=conversation_input_id,
        updated_at_ms=updated_at_ms,
    )
    return (
        sync_replace_committed_attachment_parts(
            messages=messages,
            committed=committed,
        ),
        committed.knowledge_summaries,
    )


def sync_apply_overwrite_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    messages: list[JSONDict],
    updated_at_ms: int,
    storage_root: str | None = None,
) -> tuple[list[JSONDict], list[JSONDict]]:
    references = extract_message_attachment_references(messages)
    conversation_input_id: str | None = None
    sync_validate_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        conversation_input_id=conversation_input_id,
        storage_root=storage_root,
    )
    committed = sync_commit_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        conversation_input_id=conversation_input_id,
        updated_at_ms=updated_at_ms,
    )
    unreferenced_knowledge = sync_mark_unreferenced_conversation_attachments_unused(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        updated_at_ms=updated_at_ms,
    )
    return (
        sync_replace_committed_attachment_parts(
            messages=messages,
            committed=committed,
        ),
        [*committed.knowledge_summaries, *unreferenced_knowledge],
    )
