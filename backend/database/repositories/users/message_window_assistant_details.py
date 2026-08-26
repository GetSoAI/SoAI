"""SoAI - Assistant details for cursor-window message reads [backend/database/repositories/users/message_window_assistant_details.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_to_dicts
from database.core.sqlite_values import SQLiteValue
from database.repositories.users.message_row_mapping import (
    attach_assistant_event_timeline,
)
from database.repositories.users.message_tool_projection_attachment import (
    attach_tool_call_projections,
)

__all__ = ("attach_window_assistant_details",)

_TOOL_PROJECTION_COLUMNS = (
    "id, call_id, conv_id, turn_id, iteration_index, tool_name, message_index, "
    "assistant_turn_at_ms, model_variant_index, assistant_at_ms, status, sequence_index, "
    "content_index_before, thinking_index_before, collapsed, duration_ms, started_at_ms, "
    "live_revision, last_live_event_at_ms, last_live_sequence, thinking_duration_before_ms, "
    "created_at_ms, completed_at_ms, error_message, owner_task_id, tool_arguments, tool_result"
)


def _require_json_non_negative_int(value: JSONValue | None, label: str) -> int:
    if not is_strict_int(value) or value < 0:
        raise ValidationError(f"{label} must be a non-negative integer.")
    return int(value)


def _collect_assistant_timestamps(messages: list[JSONDict]) -> list[int]:
    assistant_at_values: set[int] = set()
    for message in messages:
        timestamp = message.get("timestamp")
        if message.get("role") == "assistant" and is_strict_int(timestamp):
            assistant_at_values.add(
                _require_json_non_negative_int(timestamp, "Assistant message timestamp"),
            )
    return sorted(assistant_at_values)


def _placeholders(values: list[int]) -> str:
    return ",".join("?" for _ in values)


async def _load_assistant_event_rows(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    assistant_at_values: list[int],
) -> list[dict[str, SQLiteValue]]:
    if not assistant_at_values:
        return []
    rows: list[dict[str, SQLiteValue]] = []
    for start_index in range(0, len(assistant_at_values), SQLITE_BATCH_SIZE):
        batch = assistant_at_values[start_index : start_index + SQLITE_BATCH_SIZE]
        rows.extend(
            await query_to_dicts(
                database,
                f"""
                SELECT
                    assistant_at_ms, sequence, assistant_revision, event_type,
                    payload_json, created_at_ms
                  FROM webui_assistant_message_events
                 WHERE conv_id = ? AND assistant_at_ms IN ({_placeholders(batch)})
                ORDER BY assistant_at_ms ASC, sequence ASC, created_at_ms ASC
                """,
                (conv_id, *batch),
            ),
        )
    return rows


async def _load_tool_projection_rows(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    assistant_at_values: list[int],
) -> list[dict[str, SQLiteValue]]:
    if not assistant_at_values:
        return []
    rows: list[dict[str, SQLiteValue]] = []
    for start_index in range(0, len(assistant_at_values), SQLITE_BATCH_SIZE):
        batch = assistant_at_values[start_index : start_index + SQLITE_BATCH_SIZE]
        rows.extend(
            await query_to_dicts(
                database,
                f"""
                SELECT {_TOOL_PROJECTION_COLUMNS}
                  FROM webui_chat_tool_calls
                 WHERE conv_id = ? AND assistant_at_ms IN ({_placeholders(batch)})
                ORDER BY assistant_at_ms ASC, sequence_index ASC, created_at_ms ASC, id ASC
                """,
                (conv_id, *batch),
            ),
        )
    return rows


async def attach_window_assistant_details(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    messages: list[JSONDict],
) -> None:
    assistant_at_values = _collect_assistant_timestamps(messages)
    if not assistant_at_values:
        return
    assistant_events = await _load_assistant_event_rows(
        database,
        conv_id=conv_id,
        assistant_at_values=assistant_at_values,
    )
    attach_assistant_event_timeline(messages, assistant_events)
    tool_rows = await _load_tool_projection_rows(
        database,
        conv_id=conv_id,
        assistant_at_values=assistant_at_values,
    )
    attach_tool_call_projections(messages, tool_rows)
