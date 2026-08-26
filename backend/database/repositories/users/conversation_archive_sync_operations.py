"""SoAI - Conversation archive synchronous database operations [backend/database/repositories/users/conversation_archive_sync_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ArchivedConversationLimitError, StateError
from core.timing.epoch import epoch_ms
from database.core.row_fields import require_row_bool, require_row_non_negative_int
from database.repositories.users.conversation_sync_operations import (
    sync_get_conversation,
)
from database.repositories.users.conversation_versioning import NEXT_LAST_MODIFIED_SQL

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_update_conversation_archived",)

ARCHIVE_LIMIT = 1_000_000


def sync_update_conversation_archived(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    is_archived: bool,
) -> JSONDict | None:
    existing_cursor = conn.execute(
        "SELECT is_archived FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    existing_row = existing_cursor.fetchone()
    if not existing_row:
        return None
    current_archived = require_row_bool(
        existing_row[0],
        label="Conversation is_archived",
        build_error=StateError,
    )
    if current_archived == is_archived:
        return sync_get_conversation(conn, conv_id, user_id)
    if is_archived:
        count_cursor = conn.execute(
            "SELECT COUNT(*) FROM webui_conversations WHERE user_id = ? AND is_archived = 1",
            (user_id,),
        )
        count_row = count_cursor.fetchone()
        if not count_row:
            raise StateError("Archived conversation count is invalid.")
        archived_count = require_row_non_negative_int(
            count_row[0],
            label="Archived conversation count",
            build_error=StateError,
        )
        if archived_count >= ARCHIVE_LIMIT:
            raise ArchivedConversationLimitError("Archived conversation limit reached.")
    update_time = epoch_ms()
    if (
        conn.execute(
            f"UPDATE webui_conversations SET is_archived = ?, last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL} WHERE id = ? AND user_id = ?",
            (1 if is_archived else 0, update_time, update_time, conv_id, user_id),
        ).rowcount
        > 0
    ):
        return sync_get_conversation(conn, conv_id, user_id)
    return None
