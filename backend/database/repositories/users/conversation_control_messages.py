"""SoAI - Canonical visible conversation control records [backend/database/repositories/users/conversation_control_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.repositories.users.message_write_transactions import sync_append_messages

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_append_conversation_control_exchange",)


def _allocate_control_timestamps(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    completed_at_ms: int,
) -> tuple[int, int]:
    row = conn.execute(
        "SELECT MAX(created_at_ms) FROM webui_messages WHERE conv_id = ?",
        (conv_id,),
    ).fetchone()
    latest = row[0] if row is not None and isinstance(row[0], int) else 0
    command_at_ms = max(completed_at_ms, latest + 1)
    return (command_at_ms, command_at_ms + 1)


def sync_append_conversation_control_exchange(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    command_text: str,
    response_text: str,
    completed_at_ms: int,
) -> JSONDict:
    revision_row = conn.execute(
        "SELECT last_modified_at_ms FROM webui_conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    ).fetchone()
    if revision_row is None or not isinstance(revision_row[0], int):
        raise StateError("Conversation control target is unavailable.")
    command_at_ms, response_at_ms = _allocate_control_timestamps(
        conn,
        conv_id=conv_id,
        completed_at_ms=completed_at_ms,
    )
    result = sync_append_messages(
        conn,
        conv_id,
        user_id,
        [
            {
                "role": "user",
                "message_type": "control",
                "content": command_text,
                "timestamp": command_at_ms,
            },
            {
                "role": "assistant",
                "message_type": "control",
                "content": response_text,
                "timestamp": response_at_ms,
                "assistant_turn_at_ms": response_at_ms,
                "model_variant_index": 0,
                "assistant_event_timeline": [],
            },
        ],
        revision_row[0],
    )
    message_row = conn.execute(
        "SELECT id FROM webui_messages WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant' AND message_type = 'control'",
        (conv_id, response_at_ms),
    ).fetchone()
    if message_row is None or not isinstance(message_row[0], int):
        raise StateError("Conversation control response identity is unavailable.")
    return {
        "source_message_id": message_row[0],
        "message_count": result.message_count,
        "last_modified_at_ms": result.last_modified_at_ms,
        "command_at_ms": command_at_ms,
        "response_at_ms": response_at_ms,
    }
