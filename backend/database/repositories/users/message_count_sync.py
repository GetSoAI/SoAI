"""SoAI - Synchronous conversation message count helpers [backend/database/repositories/users/message_count_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.validation.integers import is_strict_int

__all__ = ("sync_count_stored_messages",)


def sync_count_stored_messages(conn: sqlite3.Connection, conv_id: str) -> int:
    count_row = conn.execute(
        "SELECT message_count FROM webui_conversations WHERE id = ?",
        (conv_id,),
    ).fetchone()
    if count_row is None:
        raise StateError("Stored conversation message count is invalid.")
    count_value = count_row[0]
    if not is_strict_int(count_value) or count_value < 0:
        raise StateError("Stored conversation message count is invalid.")
    return count_value
