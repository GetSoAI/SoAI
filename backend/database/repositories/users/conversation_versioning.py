"""SoAI - Monotonic conversation version helpers [backend/database/repositories/users/conversation_versioning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ConflictError, StateError
from core.timing.epoch import epoch_ms
from core.validation.epoch import require_unix_epoch_ms

__all__ = (
    "NEXT_LAST_MODIFIED_SQL",
    "sync_bump_conversation_last_modified_at_ms",
    "sync_load_conversation_last_modified_at_ms",
    "sync_require_expected_conversation_version",
)

NEXT_LAST_MODIFIED_SQL = (
    "CASE WHEN last_modified_at_ms >= ? THEN last_modified_at_ms + 1 ELSE ? END"
)


def sync_load_conversation_last_modified_at_ms(
    conn: sqlite3.Connection,
    conv_id: str,
) -> int:
    row = conn.execute(
        "SELECT last_modified_at_ms FROM webui_conversations WHERE id = ?",
        (conv_id,),
    ).fetchone()
    if row is None:
        raise StateError("Conversation version row was not found.")
    return require_unix_epoch_ms(
        row[0],
        error_message="Conversation last_modified_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )


def sync_require_expected_conversation_version(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    expected_last_modified_at_ms: int | None,
) -> int:
    current_last_modified_at_ms = sync_load_conversation_last_modified_at_ms(conn, conv_id)
    if expected_last_modified_at_ms is None:
        return current_last_modified_at_ms
    validated_expected = require_unix_epoch_ms(
        expected_last_modified_at_ms,
        error_message="Expected conversation last_modified_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    if current_last_modified_at_ms != validated_expected:
        raise ConflictError("Conversation has changed since the client loaded it.")
    return current_last_modified_at_ms


def sync_bump_conversation_last_modified_at_ms(
    conn: sqlite3.Connection,
    conv_id: str,
) -> int:
    update_time = epoch_ms()
    cursor = conn.execute(
        f"UPDATE webui_conversations SET last_modified_at_ms = {NEXT_LAST_MODIFIED_SQL} WHERE id = ?",
        (update_time, update_time, conv_id),
    )
    if cursor.rowcount <= 0:
        raise StateError("Conversation version row was not updated.")
    return sync_load_conversation_last_modified_at_ms(conn, conv_id)
