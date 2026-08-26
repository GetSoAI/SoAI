"""SoAI - Conversation attachment pending queue transitions [backend/database/repositories/users/conversation_attachment_queue_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_lookup import (
    fetch_knowledge_attachment_by_id,
)
from database.repositories.users.conversation_attachment_knowledge_readiness import (
    knowledge_attachment_ready_for_reference_params,
    knowledge_attachment_ready_for_reference_sql,
)
from database.repositories.users.conversation_attachment_references import (
    FileAttachmentReference,
    KnowledgeAttachmentReference,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("queue_file_attachment_reference", "queue_knowledge_attachment_reference")


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
        raise StateError("Queued file attachment row is missing.")
    return attachment


def queue_file_attachment_reference(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    conversation_input_id: str,
    reference: FileAttachmentReference,
    updated_at_ms: int,
) -> JSONDict:
    cursor = conn.execute(
        """
        UPDATE webui_conversation_attachments
        SET state = 'queued',
            conversation_input_id = ?,
            updated_at_ms = ?,
            attachment_revision = attachment_revision + 1
        WHERE conv_id = ?
          AND user_id = ?
          AND id = ?
          AND parse_state = 'ready'
          AND state = 'staged'
          AND conversation_input_id IS NULL
          AND attachment_revision = ?
        """,
        (
            conversation_input_id,
            updated_at_ms,
            conv_id,
            user_id,
            reference.attachment_id,
            reference.attachment_revision,
        ),
    )
    if cursor.rowcount != 1:
        raise ConflictError("File attachment changed before conversation input queue.")
    return _require_file_attachment(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=reference.attachment_id,
    )


def _require_knowledge_attachment(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict:
    summary = fetch_knowledge_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=knowledge_attachment_id,
    )
    if summary is None:
        raise StateError("Queued knowledge attachment row is missing.")
    return summary


def queue_knowledge_attachment_reference(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    conversation_input_id: str,
    reference: KnowledgeAttachmentReference,
    updated_at_ms: int,
) -> JSONDict:
    cursor = conn.execute(
        f"""
        UPDATE webui_conversation_knowledge_attachments
        SET state = 'queued',
            conversation_input_id = ?,
            updated_at_ms = ?,
            attachment_revision = attachment_revision + 1
        WHERE conv_id = ?
          AND user_id = ?
          AND id = ?
          {knowledge_attachment_ready_for_reference_sql()}
          AND state = 'draft'
          AND conversation_input_id IS NULL
          AND attachment_revision = ?
        """,
        (
            conversation_input_id,
            updated_at_ms,
            conv_id,
            user_id,
            reference.knowledge_attachment_id,
            *knowledge_attachment_ready_for_reference_params(),
            reference.attachment_revision,
        ),
    )
    if cursor.rowcount != 1:
        raise ConflictError("Knowledge attachment changed before conversation input queue.")
    return _require_knowledge_attachment(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_id=reference.knowledge_attachment_id,
    )
