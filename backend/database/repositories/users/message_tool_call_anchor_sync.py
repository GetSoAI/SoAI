"""SoAI - Tool-call anchor synchronization for stored messages [backend/database/repositories/users/message_tool_call_anchor_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_message_storage_types import (
    ConversationMessageStoragePayload,
)
from core.validation.integers import is_strict_int
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.repositories.users.message_comparison_turns import (
    build_assistant_tool_call_anchors,
)

__all__ = ("sync_tool_call_message_anchors",)


def _delete_tool_call_rows_by_assistant_at_ms_values(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms_values: list[int],
) -> None:
    for start_index in range(0, len(assistant_at_ms_values), SQLITE_BATCH_SIZE):
        batch = assistant_at_ms_values[start_index : start_index + SQLITE_BATCH_SIZE]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        conn.execute(
            f"DELETE FROM webui_tool_call_live_events WHERE conv_id = ? AND assistant_at_ms IN ({placeholders})",
            (conv_id, *batch),
        )
        conn.execute(
            f"DELETE FROM webui_chat_tool_calls WHERE conv_id = ? AND assistant_at_ms IN ({placeholders})",
            (conv_id, *batch),
        )


def sync_tool_call_message_anchors(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    validated_messages: list[ConversationMessageStoragePayload],
) -> None:
    anchors = build_assistant_tool_call_anchors(validated_messages)
    assistant_at_ms_values: list[int] = []
    for anchor in anchors:
        assistant_at_ms_values.append(anchor.assistant_at_ms)
        conn.execute(
            """
            UPDATE webui_chat_tool_calls
            SET assistant_at_ms = ?, message_index = ?
            WHERE conv_id = ? AND assistant_turn_at_ms = ? AND model_variant_index = ?
            """,
            (
                anchor.assistant_at_ms,
                anchor.logical_message_index,
                conv_id,
                anchor.assistant_turn_at_ms,
                anchor.model_variant_index,
            ),
        )
    if not assistant_at_ms_values:
        conn.execute("DELETE FROM webui_tool_call_live_events WHERE conv_id = ?", (conv_id,))
        conn.execute("DELETE FROM webui_chat_tool_calls WHERE conv_id = ?", (conv_id,))
        return
    assistant_at_ms_set = set(assistant_at_ms_values)
    existing_rows = conn.execute(
        """
        SELECT DISTINCT assistant_at_ms
        FROM webui_chat_tool_calls
        WHERE conv_id = ? AND assistant_at_ms IS NOT NULL
        """,
        (conv_id,),
    ).fetchall()
    timestamps_to_delete: list[int] = []
    for row in existing_rows:
        timestamp_value = row[0]
        if not is_strict_int(timestamp_value):
            continue
        if timestamp_value not in assistant_at_ms_set:
            timestamps_to_delete.append(timestamp_value)
    if timestamps_to_delete:
        _delete_tool_call_rows_by_assistant_at_ms_values(
            conn,
            conv_id=conv_id,
            assistant_at_ms_values=timestamps_to_delete,
        )
