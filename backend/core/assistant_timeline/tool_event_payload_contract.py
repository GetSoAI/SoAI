"""SoAI - Assistant timeline tool event payload contract [backend/core/assistant_timeline/tool_event_payload_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.assistant_timeline.tool_result_truncation import (
    truncate_tool_result_payload_for_timeline,
)
from core.errors.exceptions import ValidationError
from core.tool_calls.status_values import TOOL_CALL_PERSISTED_STATUSES
from core.validation.record_fields import (
    require_bool,
    require_int,
    require_json_object,
    require_non_empty_str,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_tool_event_payload_preview",
    "tool_event_type_requires_payload_contract",
    "validate_tool_event_payload_contract",
)

_TOOL_EVENT_TYPES: frozenset[str] = frozenset(
    (
        "tool_call_created",
        "tool_call_started",
        "tool_call_completed",
    ),
)

_REQUIRED_TOOL_FIELDS = (
    "call_id",
    "tool_name",
    "status",
    "sequence_index",
    "message_index",
    "content_index_before",
    "thinking_index_before",
    "collapsed",
)


def _require_tool_payload(value: JSONValue, *, label: str) -> JSONDict:
    return require_json_object(
        value,
        label=label,
        build_error=ValidationError,
        invalid_message=f"{label} must be an object.",
    )


def _validate_status(tool_payload: JSONDict) -> str:
    status = require_non_empty_str(
        tool_payload.get("status"),
        label="tool.status",
        build_error=ValidationError,
        invalid_message="Tool event payload status must be a non-empty string.",
    )
    if status not in TOOL_CALL_PERSISTED_STATUSES:
        raise ValidationError("Tool event payload status is invalid.")
    return status


def _copy_required_fields(source: JSONDict, target: JSONDict) -> None:
    for field_name in _REQUIRED_TOOL_FIELDS:
        target[field_name] = source[field_name]
    for field_name in (
        "assistant_turn_at_ms",
        "model_variant_index",
        "turn_id",
        "iteration_index",
        "thinking_duration_before_ms",
    ):
        value = source.get(field_name)
        if value is not None:
            target[field_name] = value


def tool_event_type_requires_payload_contract(event_type: str) -> bool:
    return event_type in _TOOL_EVENT_TYPES


def validate_tool_event_payload_contract(tool_payload: JSONDict) -> None:
    require_non_empty_str(
        tool_payload.get("call_id"),
        label="tool.call_id",
        build_error=ValidationError,
        invalid_message="Tool event payload call_id must be a non-empty string.",
    )
    require_non_empty_str(
        tool_payload.get("tool_name"),
        label="tool.tool_name",
        build_error=ValidationError,
        invalid_message="Tool event payload tool_name must be a non-empty string.",
    )
    _validate_status(tool_payload)
    require_int(
        tool_payload.get("sequence_index"),
        label="tool.sequence_index",
        build_error=ValidationError,
        minimum=0,
        invalid_message="Tool event payload sequence_index must be a non-negative integer.",
    )
    require_int(
        tool_payload.get("message_index"),
        label="tool.message_index",
        build_error=ValidationError,
        minimum=0,
        invalid_message="Tool event payload message_index must be a non-negative integer.",
    )
    require_int(
        tool_payload.get("content_index_before"),
        label="tool.content_index_before",
        build_error=ValidationError,
        minimum=0,
        invalid_message="Tool event payload content_index_before must be a non-negative integer.",
    )
    require_int(
        tool_payload.get("thinking_index_before"),
        label="tool.thinking_index_before",
        build_error=ValidationError,
        minimum=0,
        invalid_message="Tool event payload thinking_index_before must be a non-negative integer.",
    )
    require_bool(
        tool_payload.get("collapsed"),
        label="tool.collapsed",
        build_error=ValidationError,
        invalid_message="Tool event payload collapsed must be a boolean.",
    )


def build_tool_event_payload_preview(tool_payload: JSONDict) -> JSONDict:
    validate_tool_event_payload_contract(tool_payload)
    preview_value = truncate_tool_result_payload_for_timeline(tool_payload)
    preview = _require_tool_payload(preview_value, label="Tool event payload preview")
    _copy_required_fields(tool_payload, preview)
    validate_tool_event_payload_contract(preview)
    return preview
