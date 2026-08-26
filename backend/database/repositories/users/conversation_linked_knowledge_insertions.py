"""SoAI - Linked knowledge target row insertion [backend/database/repositories/users/conversation_linked_knowledge_insertions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.attachments.attachment_constants import STAGED_ATTACHMENT_TTL_MS
from core.errors.exceptions import StateError
from database.repositories.users.conversation_attachment_knowledge_counts import (
    serialize_status_counts,
)
from database.repositories.users.conversation_linked_knowledge_signature import (
    linked_state_signature,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("insert_linked_knowledge_batch",)


def _new_knowledge_attachment_id() -> str:
    return f"katt_{uuid.uuid4().hex}"


def _new_linked_document_id() -> str:
    return f"lkdoc_{uuid.uuid4().hex}"


def _summary_title(selected_items: list[JSONDict]) -> str:
    if len(selected_items) == 1:
        return str(selected_items[0]["filename"])
    return f"Linked knowledge ({len(selected_items)} documents)"


def _insert_summary(
    conn: sqlite3.Connection,
    *,
    target_conv_id: str,
    target_user_id: int,
    client_batch_id: str,
    selected_items: list[JSONDict],
    now_ms: int,
) -> str:
    knowledge_attachment_id = _new_knowledge_attachment_id()
    conn.execute(
        """
        INSERT INTO webui_conversation_knowledge_attachments (
            id, conv_id, user_id, state, conversation_input_id, message_created_at_ms,
            processing_state, source_type, operation_type, title, root_label,
            root_virtual_path, task_id, client_batch_id, first_event_id, last_event_id,
            state_signature, total_count, visible_count, hidden_count, status_counts_json,
            attachment_revision, created_at_ms, updated_at_ms, finalized_at_ms, expires_at_ms
        ) VALUES (?, ?, ?, 'draft', NULL, NULL, 'ready', 'linked_knowledge', 'added',
            ?, NULL, NULL, NULL, ?, NULL, NULL, NULL, ?, ?, 0, ?, 0, ?, ?, ?, ?)
        """,
        (
            knowledge_attachment_id,
            target_conv_id,
            target_user_id,
            _summary_title(selected_items),
            client_batch_id,
            len(selected_items),
            len(selected_items),
            serialize_status_counts({"completed": len(selected_items)}),
            now_ms,
            now_ms,
            now_ms,
            now_ms + STAGED_ATTACHMENT_TTL_MS,
        ),
    )
    return knowledge_attachment_id


def _insert_items_and_links(
    conn: sqlite3.Connection,
    *,
    target_conv_id: str,
    target_user_id: int,
    knowledge_attachment_id: str,
    client_batch_id: str,
    selected_items: list[JSONDict],
    now_ms: int,
) -> list[JSONDict]:
    child_states: list[JSONDict] = []
    for item_index, item in enumerate(selected_items):
        cursor = conn.execute(
            """
            INSERT INTO webui_conversation_knowledge_attachment_items (
                knowledge_attachment_id, conv_id, user_id, document_id, event_id,
                item_index, filename, file_type, file_size_bytes, rag_status,
                operation_type, error_message, created_at_ms
            ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, 'completed', 'added', NULL, ?)
            """,
            (
                knowledge_attachment_id,
                target_conv_id,
                target_user_id,
                item["source_document_id"],
                item_index,
                item["filename"],
                item["file_type"],
                item["file_size_bytes"],
                now_ms,
            ),
        )
        target_item_id = cursor.lastrowid
        if not isinstance(target_item_id, int) or target_item_id <= 0:
            raise StateError("Linked knowledge target item id is invalid.")
        conn.execute(
            """
            INSERT INTO rag_linked_documents (
                id, target_conv_id, target_user_id, target_knowledge_attachment_id,
                target_item_id, source_conv_id, source_user_id, source_document_id,
                source_knowledge_attachment_id, source_item_id, status,
                unavailable_reason, client_batch_id, created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', NULL, ?, ?, ?)
            """,
            (
                _new_linked_document_id(),
                target_conv_id,
                target_user_id,
                knowledge_attachment_id,
                target_item_id,
                item["source_conv_id"],
                item["source_user_id"],
                item["source_document_id"],
                item["source_knowledge_attachment_id"],
                item["source_item_id"],
                client_batch_id,
                now_ms,
                now_ms,
            ),
        )
        child_states.append(
            {
                "target_item_id": target_item_id,
                "status": "active",
                "unavailable_reason": None,
            },
        )
    return child_states


def _update_initial_state_signature(
    conn: sqlite3.Connection,
    *,
    knowledge_attachment_id: str,
    child_states: list[JSONDict],
) -> None:
    cursor = conn.execute(
        """
        UPDATE webui_conversation_knowledge_attachments
        SET state_signature = ?
        WHERE id = ?
        """,
        (
            linked_state_signature(
                active_count=len(child_states),
                unavailable_count=0,
                child_states=child_states,
            ),
            knowledge_attachment_id,
        ),
    )
    if cursor.rowcount != 1:
        raise StateError("Linked knowledge summary missing during initial signature update.")


def insert_linked_knowledge_batch(
    conn: sqlite3.Connection,
    *,
    target_conv_id: str,
    target_user_id: int,
    client_batch_id: str,
    selected_items: list[JSONDict],
    now_ms: int,
) -> str:
    knowledge_attachment_id = _insert_summary(
        conn,
        target_conv_id=target_conv_id,
        target_user_id=target_user_id,
        client_batch_id=client_batch_id,
        selected_items=selected_items,
        now_ms=now_ms,
    )
    child_states = _insert_items_and_links(
        conn,
        target_conv_id=target_conv_id,
        target_user_id=target_user_id,
        knowledge_attachment_id=knowledge_attachment_id,
        client_batch_id=client_batch_id,
        selected_items=selected_items,
        now_ms=now_ms,
    )
    _update_initial_state_signature(
        conn,
        knowledge_attachment_id=knowledge_attachment_id,
        child_states=child_states,
    )
    return knowledge_attachment_id
