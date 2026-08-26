"""SoAI - Tool call repository row mapping [backend/database/repositories/users/tool_call_row_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_event_payload_contract import (
    build_tool_event_payload_preview,
)
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from database.repositories.users.tool_call_validation import (
    parse_optional_json_from_row,
    require_non_empty_string_from_row,
    require_non_negative_integer_from_row,
    require_optional_non_negative_integer_from_row,
    validate_optional_epoch_ms_integer,
    validate_optional_string,
    validate_required_epoch_ms_integer,
    validate_status,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "format_preview_tool_call_row",
    "format_tool_call_row",
)


def format_tool_call_row(row: SQLiteRow | None) -> JSONDict | None:
    if row is None:
        return None
    storage_call_id = require_non_empty_string_from_row(row.get("id"), "id")
    call_id = require_non_empty_string_from_row(row.get("call_id"), "call_id")
    conv_id = require_non_empty_string_from_row(row.get("conv_id"), "conv_id")
    turn_id = (
        require_non_empty_string_from_row(row.get("turn_id"), "turn_id")
        if row.get("turn_id") is not None
        else None
    )
    iteration_index = require_optional_non_negative_integer_from_row(
        row.get("iteration_index"),
        "iteration_index",
    )
    tool_name = require_non_empty_string_from_row(row.get("tool_name"), "tool_name")
    message_index = require_optional_non_negative_integer_from_row(
        row.get("message_index"),
        "message_index",
    )
    assistant_turn_at_ms = validate_required_epoch_ms_integer(
        require_non_negative_integer_from_row(
            row.get("assistant_turn_at_ms"),
            "assistant_turn_at_ms",
        ),
        "assistant_turn_at_ms",
    )
    model_variant_index = require_non_negative_integer_from_row(
        row.get("model_variant_index"),
        "model_variant_index",
    )
    assistant_at_ms = validate_optional_epoch_ms_integer(
        require_optional_non_negative_integer_from_row(
            row.get("assistant_at_ms"),
            "assistant_at_ms",
        ),
        "assistant_at_ms",
    )
    status = require_non_empty_string_from_row(row.get("status"), "status")
    validate_status(status, operation="read", call_id=call_id)
    sequence_index = require_non_negative_integer_from_row(
        row.get("sequence_index"),
        "sequence_index",
    )
    content_index_before = require_non_negative_integer_from_row(
        row.get("content_index_before"),
        "content_index_before",
    )
    thinking_index_before = require_non_negative_integer_from_row(
        row.get("thinking_index_before"),
        "thinking_index_before",
    )
    collapsed_value = require_non_negative_integer_from_row(row.get("collapsed"), "collapsed")
    if collapsed_value not in (0, 1):
        raise ValidationError("Tool call field 'collapsed' must be 0 or 1.")
    duration_ms_value = require_optional_non_negative_integer_from_row(
        row.get("duration_ms"),
        "duration_ms",
    )
    duration_ms = duration_ms_value if duration_ms_value is not None else 0
    started_at_ms = validate_optional_epoch_ms_integer(
        require_optional_non_negative_integer_from_row(row.get("started_at_ms"), "started_at_ms"),
        "started_at_ms",
    )
    live_revision_value = require_optional_non_negative_integer_from_row(
        row.get("live_revision"),
        "live_revision",
    )
    live_revision = live_revision_value if live_revision_value is not None else 0
    last_live_event_at_ms = validate_optional_epoch_ms_integer(
        require_optional_non_negative_integer_from_row(
            row.get("last_live_event_at_ms"),
            "last_live_event_at_ms",
        ),
        "last_live_event_at_ms",
    )
    last_live_sequence = require_optional_non_negative_integer_from_row(
        row.get("last_live_sequence"),
        "last_live_sequence",
    )
    thinking_duration_before_ms = require_optional_non_negative_integer_from_row(
        row.get("thinking_duration_before_ms"),
        "thinking_duration_before_ms",
    )
    created_at_ms = validate_required_epoch_ms_integer(
        require_non_negative_integer_from_row(row.get("created_at_ms"), "created_at_ms"),
        "created_at_ms",
    )
    completed_at_ms = validate_optional_epoch_ms_integer(
        require_optional_non_negative_integer_from_row(
            row.get("completed_at_ms"),
            "completed_at_ms",
        ),
        "completed_at_ms",
    )
    error_message = validate_optional_string(row.get("error_message"), "error_message")
    owner_task_id = validate_optional_string(row.get("owner_task_id"), "owner_task_id")
    tool_arguments = parse_optional_json_from_row(row.get("tool_arguments"), "tool_arguments")
    tool_result = parse_optional_json_from_row(row.get("tool_result"), "tool_result")
    return {
        "id": storage_call_id,
        "call_id": call_id,
        "conv_id": conv_id,
        "turn_id": turn_id,
        "iteration_index": iteration_index,
        "message_index": message_index,
        "assistant_turn_at_ms": assistant_turn_at_ms,
        "model_variant_index": model_variant_index,
        "assistant_at_ms": assistant_at_ms,
        "tool_name": tool_name,
        "owner_task_id": owner_task_id,
        "arguments": tool_arguments,
        "result": tool_result,
        "status": status,
        "error": error_message,
        "duration_ms": duration_ms,
        "started_at_ms": started_at_ms,
        "live_revision": live_revision,
        "last_live_event_at_ms": last_live_event_at_ms,
        "last_live_sequence": last_live_sequence,
        "sequence_index": sequence_index,
        "content_index_before": content_index_before,
        "thinking_index_before": thinking_index_before,
        "thinking_duration_before_ms": thinking_duration_before_ms,
        "collapsed": collapsed_value == 1,
        "created_at_ms": created_at_ms,
        "completed_at_ms": completed_at_ms,
    }


def format_preview_tool_call_row(row: SQLiteRow | None) -> JSONDict | None:
    formatted = format_tool_call_row(row)
    if formatted is None:
        return None
    return build_tool_event_payload_preview(formatted)
