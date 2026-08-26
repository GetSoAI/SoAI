"""SoAI - Message overwrite auxiliary table reconciliation [backend/database/repositories/users/message_overwrite_reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.repositories.users.assistant_timeline_overwrite_sync import (
    sync_assistant_timelines_from_messages,
)
from database.repositories.users.message_tool_call_anchor_sync import (
    sync_tool_call_message_anchors,
)

if TYPE_CHECKING:
    from core.conversations.conversation_message_storage_types import (
        ConversationMessageStoragePayload,
    )

__all__ = ("sync_reconcile_overwritten_message_auxiliary_tables",)


def _sync_delete_orphaned_assistant_events(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    validated_messages: list[ConversationMessageStoragePayload],
) -> None:
    assistant_at_ms_values = [
        validated["created_at_ms"]
        for validated in validated_messages
        if validated.get("role") == "assistant" and isinstance(validated.get("created_at_ms"), int)
    ]
    if not assistant_at_ms_values:
        conn.execute("DELETE FROM webui_assistant_message_events WHERE conv_id = ?", (conv_id,))
        return
    assistant_at_ms_set = set(assistant_at_ms_values)
    existing_event_rows = conn.execute(
        "SELECT DISTINCT assistant_at_ms FROM webui_assistant_message_events WHERE conv_id = ?",
        (conv_id,),
    ).fetchall()
    timestamps_to_delete: list[int] = []
    for row in existing_event_rows:
        timestamp_value = row[0]
        if not is_strict_int(timestamp_value):
            continue
        if timestamp_value not in assistant_at_ms_set:
            timestamps_to_delete.append(timestamp_value)
    for start_index in range(0, len(timestamps_to_delete), SQLITE_BATCH_SIZE):
        batch = timestamps_to_delete[start_index : start_index + SQLITE_BATCH_SIZE]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        conn.execute(
            f"DELETE FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms IN ({placeholders})",
            (conv_id, *batch),
        )
    conn.execute(
        "DELETE FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms IS NULL",
        (conv_id,),
    )


def _sync_finalize_rebuilt_assistant_event_timelines(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_timestamps_to_finalize: list[int],
    finalized_at_ms: int,
) -> None:
    if not assistant_timestamps_to_finalize:
        return
    finalized_count = 0
    for start_index in range(0, len(assistant_timestamps_to_finalize), SQLITE_BATCH_SIZE):
        batch = assistant_timestamps_to_finalize[start_index : start_index + SQLITE_BATCH_SIZE]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        cursor = conn.execute(
            (
                "UPDATE webui_messages "
                "SET finalized_at_ms = ? "
                "WHERE conv_id = ? "
                "AND role = 'assistant' "
                "AND finalized_at_ms IS NULL "
                f"AND created_at_ms IN ({placeholders})"
            ),
            (finalized_at_ms, conv_id, *batch),
        )
        finalized_count += cursor.rowcount
    if finalized_count != len(assistant_timestamps_to_finalize):
        raise ValidationError("Assistant timeline rebuild finalization state is invalid.")


def sync_reconcile_overwritten_message_auxiliary_tables(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    validated_messages: list[ConversationMessageStoragePayload],
    finalized_at_ms: int,
    assistant_timestamps_to_finalize: list[int],
) -> None:
    _sync_delete_orphaned_assistant_events(
        conn,
        conv_id=conv_id,
        validated_messages=validated_messages,
    )
    sync_tool_call_message_anchors(
        conn,
        conv_id=conv_id,
        validated_messages=validated_messages,
    )
    sync_assistant_timelines_from_messages(
        conn,
        conv_id=conv_id,
        validated_messages=validated_messages,
        created_at_ms=finalized_at_ms,
    )
    _sync_finalize_rebuilt_assistant_event_timelines(
        conn,
        conv_id=conv_id,
        assistant_timestamps_to_finalize=assistant_timestamps_to_finalize,
        finalized_at_ms=finalized_at_ms,
    )
