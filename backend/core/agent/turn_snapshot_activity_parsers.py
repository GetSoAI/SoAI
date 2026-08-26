"""SoAI - Agent turn snapshot todo and tool activity parsers [backend/core/agent/turn_snapshot_activity_parsers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.todo_state_validation import VALID_TODO_ITEM_STATUSES
from core.agent.turn_snapshot_value_readers import read_json_object_list
from core.tool_calls.status_values import TOOL_CALL_PERSISTED_STATUSES
from core.validation.epoch import is_unix_epoch_ms
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_todo_items",
    "read_tool_activities",
    "read_tool_calls",
)


def read_todo_items(value: JSONValue) -> list[JSONDict] | None:
    todo_items = read_json_object_list(value)
    if todo_items is None:
        return None
    for todo_item in todo_items:
        step_value = todo_item.get("step")
        status_value = todo_item.get("status")
        if (
            not isinstance(step_value, str)
            or not step_value.strip()
            or step_value != step_value.strip()
            or not isinstance(status_value, str)
            or status_value not in VALID_TODO_ITEM_STATUSES
        ):
            return None
    return todo_items


def read_tool_calls(value: JSONValue) -> list[JSONDict] | None:
    tool_calls = read_json_object_list(value)
    if tool_calls is None:
        return None
    seen_tool_call_ids: set[str] = set()
    for tool_call in tool_calls:
        tool_call_id = tool_call.get("id")
        tool_name = tool_call.get("name")
        arguments_value = tool_call.get("arguments")
        started_at_ms = tool_call.get("started_at_ms")
        duration_ms = tool_call.get("duration_ms")
        if (
            not isinstance(tool_call_id, str)
            or not tool_call_id.strip()
            or tool_call_id != tool_call_id.strip()
        ):
            return None
        if (
            not isinstance(tool_name, str)
            or not tool_name.strip()
            or tool_name != tool_name.strip()
        ):
            return None
        if tool_call_id in seen_tool_call_ids:
            return None
        if arguments_value is not None and not isinstance(arguments_value, str | dict):
            return None
        if started_at_ms is not None and not is_unix_epoch_ms(
            started_at_ms,
            enforce_maximum=False,
        ):
            return None
        if duration_ms is not None and coerce_optional_non_negative_int_strict(duration_ms) is None:
            return None
        seen_tool_call_ids.add(tool_call_id)
    return tool_calls


def read_tool_activities(value: JSONValue) -> list[JSONDict] | None:
    activities = read_json_object_list(value)
    if activities is None:
        return None
    seen_activity_ids: set[str] = set()
    for activity in activities:
        call_id = activity.get("call_id")
        tool_name = activity.get("tool_name")
        status = activity.get("status")
        message_index = activity.get("message_index")
        sequence_index = activity.get("sequence_index")
        content_index_before = activity.get("content_index_before")
        thinking_index_before = activity.get("thinking_index_before")
        collapsed = activity.get("collapsed")
        started_sequence = activity.get("started_sequence")
        last_sequence = activity.get("last_sequence")
        text_length_before = activity.get("text_length_before")
        if not _is_valid_tool_activity_required_fields(
            call_id=call_id,
            tool_name=tool_name,
            status=status,
            message_index=message_index,
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
            collapsed=collapsed,
            started_sequence=started_sequence,
            last_sequence=last_sequence,
            text_length_before=text_length_before,
        ):
            return None
        if not isinstance(call_id, str):
            return None
        if call_id in seen_activity_ids:
            return None
        started_at_ms = activity.get("started_at_ms")
        duration_ms = activity.get("duration_ms")
        thinking_duration_before_ms = activity.get("thinking_duration_before_ms")
        error_value = activity.get("error")
        if started_at_ms is not None and not is_unix_epoch_ms(
            started_at_ms,
            enforce_maximum=False,
        ):
            return None
        if duration_ms is not None and coerce_optional_non_negative_int_strict(duration_ms) is None:
            return None
        if (
            thinking_duration_before_ms is not None
            and coerce_optional_non_negative_int_strict(thinking_duration_before_ms) is None
        ):
            return None
        if error_value is not None and not isinstance(error_value, str):
            return None
        seen_activity_ids.add(call_id)
    return activities


def _is_valid_tool_activity_required_fields(
    *,
    call_id: JSONValue,
    tool_name: JSONValue,
    status: JSONValue,
    message_index: JSONValue,
    sequence_index: JSONValue,
    content_index_before: JSONValue,
    thinking_index_before: JSONValue,
    collapsed: JSONValue,
    started_sequence: JSONValue,
    last_sequence: JSONValue,
    text_length_before: JSONValue,
) -> bool:
    if not _is_stripped_nonempty_string(call_id):
        return False
    if not _is_stripped_nonempty_string(tool_name):
        return False
    if not isinstance(status, str) or status not in TOOL_CALL_PERSISTED_STATUSES:
        return False
    if coerce_optional_non_negative_int_strict(message_index) is None:
        return False
    if coerce_optional_non_negative_int_strict(sequence_index) is None:
        return False
    if coerce_optional_non_negative_int_strict(content_index_before) is None:
        return False
    if coerce_optional_non_negative_int_strict(thinking_index_before) is None:
        return False
    if not isinstance(collapsed, bool):
        return False
    if coerce_optional_non_negative_int_strict(started_sequence) is None:
        return False
    if coerce_optional_non_negative_int_strict(last_sequence) is None:
        return False
    if not isinstance(started_sequence, int) or not isinstance(last_sequence, int):
        return False
    if last_sequence < started_sequence:
        return False
    return coerce_optional_non_negative_int_strict(text_length_before) is not None


def _is_stripped_nonempty_string(value: JSONValue) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()
