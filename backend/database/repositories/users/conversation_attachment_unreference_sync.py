"""SoAI - Conversation attachment overwrite unreference transitions [backend/database/repositories/users/conversation_attachment_unreference_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.repositories.users.conversation_attachment_references import (
    ConversationAttachmentReferences,
)
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_mark_unreferenced_conversation_attachments_unused",)


def _referenced_file_ids(references: ConversationAttachmentReferences) -> set[str]:
    return {reference.attachment_id for reference in references.files}


def _referenced_knowledge_ids(references: ConversationAttachmentReferences) -> set[str]:
    return {reference.knowledge_attachment_id for reference in references.knowledge}


def _fetch_committed_ids(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    id_column: str,
    conv_id: str,
    user_id: int,
) -> list[str]:
    rows = conn.execute(
        f"SELECT {id_column} FROM {table_name} WHERE conv_id = ? AND user_id = ? AND state = 'committed'",
        (conv_id, user_id),
    ).fetchall()
    committed_ids: list[str] = []
    for row in rows:
        value = row[0]
        if not isinstance(value, str) or not value.strip():
            raise ConflictError("Committed attachment row has invalid identity.")
        committed_ids.append(value)
    return committed_ids


def _mark_unreferenced_rows_unused(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    id_column: str,
    conv_id: str,
    user_id: int,
    referenced_ids: set[str],
    updated_at_ms: int,
) -> list[str]:
    committed_ids = _fetch_committed_ids(
        conn,
        table_name=table_name,
        id_column=id_column,
        conv_id=conv_id,
        user_id=user_id,
    )
    stale_ids = [
        committed_id for committed_id in committed_ids if committed_id not in referenced_ids
    ]
    for start_index in range(0, len(stale_ids), SQLITE_BATCH_SIZE):
        batch = stale_ids[start_index : start_index + SQLITE_BATCH_SIZE]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        conn.execute(
            f"""
            UPDATE {table_name}
            SET state = 'unused',
                conversation_input_id = NULL,
                message_created_at_ms = NULL,
                updated_at_ms = ?,
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ?
              AND user_id = ?
              AND {id_column} IN ({placeholders})
              AND state = 'committed'
            """,
            (updated_at_ms, conv_id, user_id, *batch),
        )
    return stale_ids


def _load_knowledge_summaries(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_ids: list[str],
) -> list[JSONDict]:
    if not knowledge_attachment_ids:
        return []
    placeholders = ",".join("?" for _ in knowledge_attachment_ids)
    rows = conn.execute(
        f"""
        SELECT *
        FROM webui_conversation_knowledge_attachments
        WHERE conv_id = ?
          AND user_id = ?
          AND id IN ({placeholders})
        """,
        (conv_id, user_id, *knowledge_attachment_ids),
    ).fetchall()
    summaries: list[JSONDict] = []
    for row in rows:
        summary = format_knowledge_attachment_row(row)
        if summary is not None:
            summaries.append(summary)
    return summaries


def sync_mark_unreferenced_conversation_attachments_unused(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    references: ConversationAttachmentReferences,
    updated_at_ms: int,
) -> list[JSONDict]:
    _mark_unreferenced_rows_unused(
        conn,
        table_name="webui_conversation_attachments",
        id_column="id",
        conv_id=conv_id,
        user_id=user_id,
        referenced_ids=_referenced_file_ids(references),
        updated_at_ms=updated_at_ms,
    )
    stale_knowledge_ids = _mark_unreferenced_rows_unused(
        conn,
        table_name="webui_conversation_knowledge_attachments",
        id_column="id",
        conv_id=conv_id,
        user_id=user_id,
        referenced_ids=_referenced_knowledge_ids(references),
        updated_at_ms=updated_at_ms,
    )
    return _load_knowledge_summaries(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        knowledge_attachment_ids=stale_knowledge_ids,
    )
