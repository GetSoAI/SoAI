"""SoAI - Tool call live event chronology resolution [backend/database/repositories/users/tool_call_live_chronology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.requests import RecordToolCallLiveEventRequest
from core.errors.exceptions import ValidationError
from core.types.json import is_json_dict
from database.core.json_codec import safe_json_deserialize_required_object
from database.repositories.users.tool_call_chronology_validation import (
    resolve_tool_call_content_anchor_against_assistant_message,
)
from database.repositories.users.tool_call_validation import (
    validate_non_negative_integer,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("validate_live_projection_chronology",)


def _load_live_event_tool_payload(request: RecordToolCallLiveEventRequest) -> JSONDict:
    payload = safe_json_deserialize_required_object(
        request.payload_json,
        error_message="Tool live event payload_json must decode to an object.",
    )
    tool_payload = payload.get("tool")
    if not is_json_dict(tool_payload):
        raise ValidationError("Tool live event payload_json must contain a tool object.")
    return tool_payload


def _require_live_chronology_value(tool_payload: JSONDict, field_name: str) -> int:
    value = validate_non_negative_integer(tool_payload.get(field_name), field_name)
    if value is None:
        raise ValidationError(f"Tool live event field '{field_name}' is required.")
    return value


def _require_projection_chronology_value(
    projection_row: SQLiteRowDict,
    field_name: str,
) -> int:
    value = validate_non_negative_integer(projection_row.get(field_name), field_name)
    if value is None:
        raise ValidationError(f"Tool projection field '{field_name}' is required.")
    return value


def validate_live_projection_chronology(
    *,
    conn: sqlite3.Connection,
    request: RecordToolCallLiveEventRequest,
    projection_row: SQLiteRowDict,
    conv_id: str,
    assistant_turn_at_ms: int,
    model_variant_index: int,
) -> None:
    tool_payload = _load_live_event_tool_payload(request)
    sequence_index = _require_live_chronology_value(tool_payload, "sequence_index")
    content_index_before = _require_live_chronology_value(
        tool_payload,
        "content_index_before",
    )
    thinking_index_before = _require_live_chronology_value(
        tool_payload,
        "thinking_index_before",
    )
    persisted_sequence_index = _require_projection_chronology_value(
        projection_row,
        "sequence_index",
    )
    persisted_content_index_before = _require_projection_chronology_value(
        projection_row,
        "content_index_before",
    )
    persisted_thinking_index_before = _require_projection_chronology_value(
        projection_row,
        "thinking_index_before",
    )
    if (
        persisted_sequence_index != sequence_index
        or persisted_content_index_before != content_index_before
        or persisted_thinking_index_before != thinking_index_before
    ):
        raise ValidationError("Tool live event chronology conflicts with projection row.")
    resolved_persisted_content_index_before = (
        resolve_tool_call_content_anchor_against_assistant_message(
            conn,
            conv_id=conv_id,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            content_index_before=persisted_content_index_before,
        )
    )
    if resolved_persisted_content_index_before != persisted_content_index_before:
        raise ValidationError("Tool live event chronology conflicts with projection row.")
