"""SoAI - Knowledge attachment creation transactions [backend/database/repositories/users/conversation_attachment_knowledge_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.attachments.knowledge_attachment_states import (
    KNOWLEDGE_DRAFT_ATTACHMENT_STATE,
)
from core.errors.exceptions import ConflictError, StateError
from database.repositories.users.conversation_attachment_knowledge_counts import (
    empty_status_counts,
    serialize_status_counts,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_client_batch,
    fetch_knowledge_attachment_by_id,
    map_knowledge_attachment_integrity_error,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_ensure_knowledge_attachment",)


def _new_knowledge_attachment_id() -> str:
    return f"katt_{uuid.uuid4().hex}"


def _require_matching_client_batch(
    existing: JSONDict,
    *,
    source_type: str,
    operation_type: str,
    title: str,
    root_label: str | None,
    root_virtual_path: str | None,
    task_id: str | None,
) -> JSONDict:
    required_matches = (
        ("source_type", source_type),
        ("operation_type", operation_type),
        ("title", title),
        ("root_label", root_label),
        ("root_virtual_path", root_virtual_path),
        ("state", KNOWLEDGE_DRAFT_ATTACHMENT_STATE),
    )
    for field_name, expected_value in required_matches:
        if existing.get(field_name) != expected_value:
            raise ConflictError("Knowledge attachment client batch is already bound.")
    if task_id is not None and existing.get("task_id") != task_id:
        raise ConflictError("Knowledge attachment client batch is already bound.")
    return existing


def sync_ensure_knowledge_attachment(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    source_type: str,
    operation_type: str,
    title: str,
    root_label: str | None,
    root_virtual_path: str | None,
    task_id: str | None,
    client_batch_id: str | None,
    created_at_ms: int,
    expires_at_ms: int,
) -> JSONDict:
    if client_batch_id is not None:
        existing = fetch_knowledge_attachment_by_client_batch(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            client_batch_id=client_batch_id,
        )
        if existing is not None:
            return _require_matching_client_batch(
                existing,
                source_type=source_type,
                operation_type=operation_type,
                title=title,
                root_label=root_label,
                root_virtual_path=root_virtual_path,
                task_id=task_id,
            )
    knowledge_attachment_id = _new_knowledge_attachment_id()
    try:
        conn.execute(
            """
            INSERT INTO webui_conversation_knowledge_attachments (
                id, conv_id, user_id, state, conversation_input_id, message_created_at_ms,
                processing_state, source_type, operation_type, title, root_label,
                root_virtual_path, task_id, client_batch_id, first_event_id, last_event_id,
                state_signature, total_count, visible_count, hidden_count, status_counts_json,
                attachment_revision, created_at_ms, updated_at_ms, finalized_at_ms, expires_at_ms
            ) VALUES (?, ?, ?, 'draft', NULL, NULL, 'pending', ?, ?, ?, ?, ?, ?, ?, NULL,
                NULL, NULL, 0, 0, 0, ?, 0, ?, ?, NULL, ?)
            """,
            (
                knowledge_attachment_id,
                conv_id,
                user_id,
                source_type,
                operation_type,
                title,
                root_label,
                root_virtual_path,
                task_id,
                client_batch_id,
                serialize_status_counts(empty_status_counts()),
                created_at_ms,
                created_at_ms,
                expires_at_ms,
            ),
        )
    except sqlite3.IntegrityError as exception:
        if client_batch_id is not None:
            existing = fetch_knowledge_attachment_by_client_batch(
                conn,
                conv_id=conv_id,
                user_id=user_id,
                client_batch_id=client_batch_id,
            )
            if existing is not None:
                return _require_matching_client_batch(
                    existing,
                    source_type=source_type,
                    operation_type=operation_type,
                    title=title,
                    root_label=root_label,
                    root_virtual_path=root_virtual_path,
                    task_id=task_id,
                )
        raise map_knowledge_attachment_integrity_error(exception) from exception
    inserted = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if inserted is None:
        raise StateError("Knowledge attachment row missing after insert.")
    return inserted
