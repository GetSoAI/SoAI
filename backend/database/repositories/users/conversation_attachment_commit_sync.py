"""SoAI - Conversation attachment commit canonicalization [backend/database/repositories/users/conversation_attachment_commit_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from core.attachments.attachment_content_parts import (
    content_part_from_file_attachment,
    content_part_from_knowledge_summary,
)
from core.types.json import JSONDict, JSONValue
from database.repositories.users.conversation_attachment_file_commit import (
    commit_file_attachment_reference,
)
from database.repositories.users.conversation_attachment_knowledge_commit import (
    commit_knowledge_attachment_reference,
)
from database.repositories.users.conversation_attachment_references import (
    ConversationAttachmentReferences,
)

__all__ = (
    "CommittedAttachmentContent",
    "sync_commit_attachment_references",
    "sync_replace_committed_attachment_parts",
)


@dataclass(frozen=True, slots=True)
class CommittedAttachmentContent:
    files: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    knowledge: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    knowledge_summaries: list[JSONDict] = field(default_factory=list[JSONDict])


def sync_commit_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    references: ConversationAttachmentReferences,
    conversation_input_id: str | None,
    updated_at_ms: int,
) -> CommittedAttachmentContent:
    file_parts: dict[str, JSONDict] = {}
    knowledge_parts: dict[str, JSONDict] = {}
    knowledge_summaries: list[JSONDict] = []
    for file_reference in references.files:
        attachment = commit_file_attachment_reference(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            reference=file_reference,
            conversation_input_id=conversation_input_id,
            updated_at_ms=updated_at_ms,
        )
        file_parts[file_reference.attachment_id] = content_part_from_file_attachment(attachment)
    for knowledge_reference in references.knowledge:
        summary = commit_knowledge_attachment_reference(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            reference=knowledge_reference,
            conversation_input_id=conversation_input_id,
            updated_at_ms=updated_at_ms,
        )
        knowledge_parts[knowledge_reference.knowledge_attachment_id] = (
            content_part_from_knowledge_summary(summary)
        )
        knowledge_summaries.append(summary)
    return CommittedAttachmentContent(
        files=file_parts,
        knowledge=knowledge_parts,
        knowledge_summaries=knowledge_summaries,
    )


def sync_replace_committed_attachment_parts(
    *,
    messages: list[JSONDict],
    committed: CommittedAttachmentContent,
) -> list[JSONDict]:
    if not committed.files and not committed.knowledge:
        return [dict(message) for message in messages]
    canonical_messages: list[JSONDict] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            canonical_messages.append(dict(message))
            continue
        canonical_content: list[JSONValue] = []
        for entry in content:
            if isinstance(entry, dict) and entry.get("type") == "soai_file":
                attachment_id = entry.get("attachment_id")
                if isinstance(attachment_id, str) and attachment_id in committed.files:
                    canonical_content.append(committed.files[attachment_id])
                    continue
            if isinstance(entry, dict) and entry.get("type") == "soai_knowledge":
                knowledge_attachment_id = entry.get("knowledge_attachment_id")
                if (
                    isinstance(knowledge_attachment_id, str)
                    and knowledge_attachment_id in committed.knowledge
                ):
                    canonical_content.append(committed.knowledge[knowledge_attachment_id])
                    continue
            canonical_content.append(entry)
        canonical_message = dict(message)
        canonical_message["content"] = canonical_content
        canonical_messages.append(canonical_message)
    return canonical_messages
