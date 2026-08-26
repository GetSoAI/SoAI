"""SoAI - File attachment lookup helpers [backend/database/repositories/users/conversation_attachment_file_lookup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_attachment_rows import (
    format_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("fetch_file_attachment_by_id",)


def fetch_file_attachment_by_id(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    attachment_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT *
            FROM webui_conversation_attachments
            WHERE conv_id = ? AND user_id = ? AND id = ?
            """,
            (conv_id, user_id, attachment_id),
        ),
    )
    return format_attachment_row(row)
