"""SoAI - Conversation ownership validation helper [backend/database/repositories/users/conversation_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from database.core.query_execution import sync_fetch_one_as_dict

__all__ = ("ensure_conversation_owned",)


def ensure_conversation_owned(conn: sqlite3.Connection, conv_id: str, user_id: int) -> None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT 1 AS found FROM webui_conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ),
    )
    if row is None:
        raise ValidationError("Conversation not found or access denied.")
