"""SoAI - Canonical agent prompt history reconstruction [backend/database/repositories/users/agent_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD,
)
from core.tool_calls.status_values import is_terminal_tool_call_status
from core.validation.integers import is_strict_int
from database.repositories.users.assistant_turn_history_projection import (
    build_visible_history_message,
    project_assistant_turn_history_messages,
)
from database.repositories.users.message_row_mapping import (
    build_message_payload_from_row,
)
from database.repositories.users.prompt_compaction_projection import (
    build_prompt_compaction_projections,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRow

__all__ = ("build_canonical_agent_history",)


def _resolve_unique_assistant_logical_message_index(
    *,
    timestamp_value: JSONValue,
    assistant_logical_message_indexes_by_timestamp: dict[int, list[int]],
) -> int | None:
    if is_strict_int(timestamp_value):
        matching_logical_indexes = assistant_logical_message_indexes_by_timestamp.get(
            timestamp_value,
        )
        if matching_logical_indexes is not None and len(matching_logical_indexes) == 1:
            return matching_logical_indexes[0]
    return None


def _resolve_anchor_logical_message_index(
    *,
    tool_call: Mapping[str, JSONValue],
    assistant_logical_message_indexes: set[int],
    assistant_logical_message_indexes_by_timestamp: dict[int, list[int]],
) -> int | None:
    message_index = tool_call.get("message_index")
    if (
        isinstance(message_index, int)
        and not isinstance(message_index, bool)
        and message_index in assistant_logical_message_indexes
    ):
        return message_index
    anchor_index = _resolve_unique_assistant_logical_message_index(
        timestamp_value=tool_call.get("assistant_at_ms"),
        assistant_logical_message_indexes_by_timestamp=(
            assistant_logical_message_indexes_by_timestamp
        ),
    )
    if anchor_index is not None:
        return anchor_index
    return _resolve_unique_assistant_logical_message_index(
        timestamp_value=tool_call.get("assistant_turn_at_ms"),
        assistant_logical_message_indexes_by_timestamp=(
            assistant_logical_message_indexes_by_timestamp
        ),
    )


def _build_assistant_logical_message_indexes(
    stored_messages: Sequence[JSONDict],
) -> tuple[set[int], dict[int, list[int]]]:
    assistant_logical_message_indexes: set[int] = set()
    assistant_logical_message_indexes_by_timestamp: dict[int, list[int]] = {}
    logical_message_index = 0
    for message_payload in stored_messages:
        role_value = message_payload.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role == "system":
            continue
        if role != "assistant":
            logical_message_index += 1
            continue
        timestamp_value = message_payload.get("timestamp")
        if is_strict_int(timestamp_value):
            assistant_logical_message_indexes.add(logical_message_index)
            matching_indexes = assistant_logical_message_indexes_by_timestamp.get(timestamp_value)
            if matching_indexes is None:
                assistant_logical_message_indexes_by_timestamp[timestamp_value] = [
                    logical_message_index,
                ]
            else:
                matching_indexes.append(logical_message_index)
        logical_message_index += 1
    return (
        assistant_logical_message_indexes,
        assistant_logical_message_indexes_by_timestamp,
    )


def build_canonical_agent_history(
    *,
    message_rows: Sequence[SQLiteRow],
    tool_call_rows: Sequence[JSONDict],
    compaction_event_rows: Sequence[SQLiteRow] = (),
) -> list[JSONDict]:
    stored_messages = [build_message_payload_from_row(row) for row in message_rows]
    compaction_projections = build_prompt_compaction_projections(
        tool_call_rows=tool_call_rows,
        assistant_event_rows=compaction_event_rows,
    )
    if compaction_projections:
        for message_payload in stored_messages:
            timestamp_value = message_payload.get("timestamp")
            if not is_strict_int(timestamp_value):
                continue
            projection = compaction_projections.get(timestamp_value)
            if projection is None:
                continue
            message_payload["soai_compaction"] = dict(projection.marker)
            message_payload[CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD] = (
                projection.post_compaction_text
            )
    (
        assistant_logical_message_indexes,
        assistant_logical_message_indexes_by_timestamp,
    ) = _build_assistant_logical_message_indexes(stored_messages)
    tool_calls_by_logical_message_index: dict[int, list[JSONDict]] = {}
    for tool_call in tool_call_rows:
        status_value = tool_call.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if not is_terminal_tool_call_status(status):
            continue
        anchor_logical_message_index = _resolve_anchor_logical_message_index(
            tool_call=tool_call,
            assistant_logical_message_indexes=assistant_logical_message_indexes,
            assistant_logical_message_indexes_by_timestamp=(
                assistant_logical_message_indexes_by_timestamp
            ),
        )
        if anchor_logical_message_index is None:
            continue
        tool_call_payload = dict(tool_call)
        matching_tool_calls = tool_calls_by_logical_message_index.get(anchor_logical_message_index)
        if matching_tool_calls is None:
            tool_calls_by_logical_message_index[anchor_logical_message_index] = [tool_call_payload]
        else:
            matching_tool_calls.append(tool_call_payload)
    history: list[JSONDict] = []
    logical_message_index = 0
    for message_payload in stored_messages:
        role_value = message_payload.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role == "system":
            history.append(build_visible_history_message(message_payload))
            continue
        if role != "assistant":
            history.append(build_visible_history_message(message_payload))
            logical_message_index += 1
            continue
        anchored_tool_calls = tool_calls_by_logical_message_index.get(
            logical_message_index,
            [],
        )
        history.extend(
            project_assistant_turn_history_messages(
                message_payload=message_payload,
                anchored_tool_calls=anchored_tool_calls,
            ),
        )
        logical_message_index += 1
    return history
