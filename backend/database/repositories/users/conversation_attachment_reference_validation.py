"""SoAI - Conversation attachment reference validation [backend/database/repositories/users/conversation_attachment_reference_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError
from core.serialization.json import serialize_json_compact_stable
from database.repositories.users.conversation_attachment_file_availability import (
    sync_require_attachment_file_available,
)
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
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
)
from database.repositories.users.conversation_attachment_references import (
    ConversationAttachmentReferences,
    FileAttachmentReference,
    KnowledgeAttachmentReference,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_validate_attachment_references",
    "sync_validate_nonqueued_attachment_references",
)


def _require_unique_references(references: ConversationAttachmentReferences) -> None:
    file_ids: set[str] = set()
    for file_reference in references.files:
        if file_reference.attachment_id in file_ids:
            raise ConflictError("Duplicate file attachment reference.")
        file_ids.add(file_reference.attachment_id)
    knowledge_ids: set[str] = set()
    for knowledge_reference in references.knowledge:
        if knowledge_reference.knowledge_attachment_id in knowledge_ids:
            raise ConflictError("Duplicate knowledge attachment reference.")
        knowledge_ids.add(knowledge_reference.knowledge_attachment_id)


def _fetch_file_attachment(
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
        raise ConflictError("File attachment is not available.")
    return attachment


def _fetch_knowledge_attachment(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict:
    attachment = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if attachment is None:
        raise ConflictError("Knowledge attachment is not available.")
    return attachment


def _require_file_metadata_matches(reference: FileAttachmentReference, row: JSONDict) -> None:
    comparisons = (
        ("file_id", reference.file_id),
        ("filename", reference.filename),
        ("mime_type", reference.mime_type),
        ("size_bytes", reference.size_bytes),
        ("preview_type", reference.preview_type),
        ("created_at_ms", reference.created_at_ms),
    )
    for field_name, expected in comparisons:
        if row.get(field_name) != expected:
            raise ConflictError("File attachment metadata changed before message write.")
    if (
        row.get("state") == "committed"
        and row.get("message_created_at_ms") == reference.message_created_at_ms
    ):
        return
    if row.get("attachment_revision") != reference.attachment_revision:
        raise ConflictError("File attachment metadata changed before message write.")


def _require_file_state(
    row: JSONDict,
    *,
    conversation_input_id: str | None,
) -> None:
    if row.get("parse_state") != "ready":
        raise ConflictError("File attachment is not ready.")
    state = row.get("state")
    if state == "committed" and row.get("conversation_input_id") is None:
        return
    if state == "staged" and conversation_input_id is None:
        return
    if (
        state == "queued"
        and conversation_input_id is not None
        and row.get("conversation_input_id") == conversation_input_id
    ):
        return
    raise ConflictError("File attachment is not committable.")


def _require_knowledge_metadata_matches(
    reference: KnowledgeAttachmentReference,
    row: JSONDict,
) -> None:
    comparisons = (
        ("summary_id", reference.summary_id),
        ("source_type", reference.source_type),
        ("operation_type", reference.operation_type),
        ("title", reference.title),
        ("total_count", reference.total_count),
        ("visible_count", reference.visible_count),
        ("hidden_count", reference.hidden_count),
        ("first_event_id", reference.first_event_id),
        ("last_event_id", reference.last_event_id),
        ("created_at_ms", reference.created_at_ms),
        ("finalized_at_ms", reference.finalized_at_ms),
    )
    for field_name, expected in comparisons:
        if row.get(field_name) != expected:
            raise ConflictError("Knowledge attachment metadata changed before message write.")
    if serialize_json_compact_stable(reference.status_counts) != serialize_json_compact_stable(
        row.get("status_counts"),
    ):
        raise ConflictError("Knowledge attachment status counts changed before message write.")
    if (
        row.get("state") == "committed"
        and row.get("message_created_at_ms") == reference.message_created_at_ms
    ):
        return
    if row.get("attachment_revision") != reference.attachment_revision:
        raise ConflictError("Knowledge attachment metadata changed before message write.")


def _require_no_nonterminal_knowledge_items(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> None:
    if sync_knowledge_attachment_has_active_items(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    ):
        raise ConflictError("Knowledge attachment still has active items.")


def _require_knowledge_state(
    row: JSONDict,
    *,
    conversation_input_id: str | None,
) -> None:
    if not knowledge_attachment_processing_state_ready(row.get("processing_state")):
        raise ConflictError("Knowledge attachment is not ready.")
    if not knowledge_attachment_has_completed_items(row):
        raise ConflictError("Knowledge attachment has no completed items.")
    if not knowledge_attachment_has_finalized_timestamp(row):
        raise ConflictError("Knowledge attachment is not finalized.")
    state = row.get("state")
    if state == "committed" and row.get("conversation_input_id") is None:
        return
    if state == "draft" and conversation_input_id is None:
        return
    if (
        state == "queued"
        and conversation_input_id is not None
        and row.get("conversation_input_id") == conversation_input_id
    ):
        return
    raise ConflictError("Knowledge attachment is not committable.")


def sync_validate_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    references: ConversationAttachmentReferences,
    conversation_input_id: str | None,
    storage_root: str | None = None,
) -> None:
    _require_unique_references(references)
    for file_reference in references.files:
        row = _fetch_file_attachment(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            attachment_id=file_reference.attachment_id,
        )
        _require_file_metadata_matches(file_reference, row)
        sync_require_attachment_file_available(
            conn,
            file_id=file_reference.file_id,
            user_id=user_id,
            size_bytes=file_reference.size_bytes,
            storage_root=storage_root,
        )
        _require_file_state(row, conversation_input_id=conversation_input_id)
    for knowledge_reference in references.knowledge:
        row = _fetch_knowledge_attachment(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_reference.knowledge_attachment_id,
        )
        _require_knowledge_metadata_matches(knowledge_reference, row)
        _require_knowledge_state(row, conversation_input_id=conversation_input_id)
        _require_no_nonterminal_knowledge_items(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            knowledge_attachment_id=knowledge_reference.knowledge_attachment_id,
        )


def sync_validate_nonqueued_attachment_references(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    references: ConversationAttachmentReferences,
    storage_root: str | None = None,
) -> None:
    sync_validate_attachment_references(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        references=references,
        conversation_input_id=None,
        storage_root=storage_root,
    )
