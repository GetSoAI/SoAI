"""SoAI - Conversation attachment commit canonicalization [backend/database/repositories/users/conversation_attachment_commit_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections import Counter, deque
from dataclasses import dataclass, field

from core.attachments.attachment_content_parts import (
    content_part_from_file_attachment,
    content_part_from_knowledge_summary,
    content_part_from_unavailable_file,
)
from core.attachments.attachment_content_validation import (
    validate_soai_file_content_part,
    validate_soai_file_unavailable_content_part,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
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
    "sync_restore_unavailable_file_references",
)


@dataclass(frozen=True, slots=True)
class CommittedAttachmentContent:
    files: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    knowledge: dict[str, JSONDict] = field(default_factory=dict[str, JSONDict])
    knowledge_summaries: list[JSONDict] = field(default_factory=list[JSONDict])


def sync_restore_unavailable_file_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    created_at_ms: int,
    message_id: int | None,
    content: JSONValue,
) -> JSONValue:
    if not isinstance(content, list) or not any(
        isinstance(part, dict) and part.get("type") == "soai_file_unavailable" for part in content
    ):
        return content
    row = conn.execute(
        """
        SELECT content FROM webui_messages
        WHERE conv_id = ? AND created_at_ms = ? AND role = 'user' AND message_type = 'chat'
          AND (? IS NULL OR id = ?)
        """,
        (conv_id, created_at_ms, message_id, message_id),
    ).fetchone()
    if row is None:
        return content
    stored = parse_json_value(row[0])
    if not isinstance(stored, list):
        return content
    content = [
        (
            validate_soai_file_unavailable_content_part(part)
            if isinstance(part, dict) and part.get("type") == "soai_file_unavailable"
            else part
        )
        for part in content
    ]
    explicit_ids: Counter[str] = Counter()
    snapshot_counts: Counter[str] = Counter()
    for part in content:
        if isinstance(part, dict) and part.get("type") == "soai_file":
            attachment_id = part.get("attachment_id")
            if isinstance(attachment_id, str):
                explicit_ids[attachment_id] += 1
        elif isinstance(part, dict) and part.get("type") == "soai_file_unavailable":
            snapshot_counts[serialize_json_compact_stable_strict(part)] += 1
    candidates_by_snapshot: dict[str, deque[JSONDict]] = {}
    for part in stored:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "soai_file":
            canonical = validate_soai_file_content_part(part)
            attachment_id = str(canonical["attachment_id"])
            if explicit_ids[attachment_id] > 0:
                explicit_ids[attachment_id] -= 1
                continue
            snapshot = content_part_from_unavailable_file(canonical)
        elif part.get("type") == "soai_file_unavailable":
            canonical = validate_soai_file_unavailable_content_part(part)
            snapshot = canonical
        else:
            continue
        key = serialize_json_compact_stable_strict(snapshot)
        if key not in candidates_by_snapshot:
            candidates_by_snapshot[key] = deque()
        candidates_by_snapshot[key].append(canonical)
    for key, candidates in candidates_by_snapshot.items():
        if (
            snapshot_counts[key]
            and len(candidates) != snapshot_counts[key]
            and any(candidate != candidates[0] for candidate in candidates)
        ):
            raise ValidationError(
                "Attachment references are ambiguous. Reload the conversation before editing."
            )
    restored: list[JSONValue] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "soai_file_unavailable":
            restored.append(part)
            continue
        matching_candidates = candidates_by_snapshot.get(serialize_json_compact_stable_strict(part))
        if matching_candidates:
            restored.append(dict(matching_candidates.popleft()))
        else:
            restored.append(part)
    return restored


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
