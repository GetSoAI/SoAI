"""SoAI - Knowledge attachment deletion transactions [backend/database/repositories/users/conversation_attachment_knowledge_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_delete_knowledge_attachment_by_id",)


def sync_delete_knowledge_attachment_by_id(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            DELETE FROM webui_conversation_knowledge_attachments
            WHERE conv_id = ? AND user_id = ? AND id = ?
            RETURNING *
            """,
            (conv_id, user_id, knowledge_attachment_id),
        ),
    )
    if row is None:
        return None
    deleted = format_knowledge_attachment_row(row)
    if deleted is None:
        raise ConflictError("Knowledge attachment is no longer available.")
    return deleted
