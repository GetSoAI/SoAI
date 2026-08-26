"""SoAI - Assistant event sequence resolution for streaming timelines [backend/database/repositories/users/assistant_event_sequence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_optional_int_from_sqlite_row

__all__ = ("resolve_next_assistant_event_sequence",)


def resolve_next_assistant_event_sequence(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
) -> int:
    assistant_row = sync_fetch_one_as_dict(
        conn.execute(
            (
                "SELECT finalized_at_ms FROM webui_messages "
                "WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant'"
            ),
            (conv_id, assistant_at_ms),
        ),
    )
    if assistant_row is None:
        raise ValidationError("Streaming assistant message not found.")
    if assistant_row.get("finalized_at_ms") is not None:
        raise ValidationError("Streaming assistant message is already finalized.")
    latest_sequence_row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT MAX(sequence) AS sequence FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms = ?",
            (conv_id, assistant_at_ms),
        ),
    )
    latest_sequence_value = (
        coerce_optional_int_from_sqlite_row(latest_sequence_row, "sequence")
        if latest_sequence_row
        else None
    )
    if latest_sequence_value is None:
        return 0
    if (
        isinstance(latest_sequence_value, bool)
        or not isinstance(latest_sequence_value, int)
        or latest_sequence_value < 0
    ):
        raise ValidationError("Stored assistant event sequence must be a non-negative integer.")
    return latest_sequence_value + 1
