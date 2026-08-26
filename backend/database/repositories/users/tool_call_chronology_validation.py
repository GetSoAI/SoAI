"""SoAI - Tool call chronology persistence validation [backend/database/repositories/users/tool_call_chronology_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.chronology import bound_required_chronology_anchor
from core.validation.integers import is_strict_int
from database.core.json_codec import safe_json_deserialize
from database.repositories.users.assistant_event_chronology_validation import (
    resolve_persisted_assistant_visible_length,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteValue

__all__ = ("resolve_tool_call_content_anchor_against_assistant_message",)


def _resolve_assistant_text_length(value: SQLiteValue | None) -> int:
    decoded = safe_json_deserialize(value, "")
    if isinstance(decoded, str):
        return len(decoded)
    raise ValidationError("Assistant message content must decode to a string.")


def resolve_tool_call_content_anchor_against_assistant_message(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    content_index_before: int,
) -> int:
    row = conn.execute(
        """
        SELECT content, created_at_ms, finalized_at_ms
        FROM webui_messages
        WHERE conv_id = ?
          AND role = 'assistant'
          AND assistant_turn_at_ms = ?
          AND model_variant_index = ?
        LIMIT 1
        """,
        (conv_id, assistant_turn_at_ms, model_variant_index),
    ).fetchone()
    if row is None:
        raise ValidationError("Tool call assistant message row was not found.")
    assistant_at_ms = row[1]
    if not is_strict_int(assistant_at_ms):
        raise ValidationError("Tool call assistant message timestamp is invalid.")
    message_visible_length = _resolve_assistant_text_length(row[0])
    finalized_at_ms = row[2]
    visible_length = message_visible_length
    if finalized_at_ms is None:
        visible_length = max(
            message_visible_length,
            resolve_persisted_assistant_visible_length(
                conn,
                conv_id=conv_id,
                assistant_at_ms=assistant_at_ms,
            ),
        )
    elif not is_strict_int(finalized_at_ms):
        raise ValidationError("Tool call assistant message finalization timestamp is invalid.")
    return bound_required_chronology_anchor(
        content_index_before,
        "content_index_before",
        upper_bound=visible_length,
    )
