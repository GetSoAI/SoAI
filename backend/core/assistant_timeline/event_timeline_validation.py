"""SoAI - Assistant message event timeline validation [backend/core/assistant_timeline/event_timeline_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, NoReturn

from core.assistant_timeline.thinking_payload_validation import (
    validate_thinking_phase_payload_contract,
)
from core.assistant_timeline.tool_sequence_ownership import (
    register_tool_call_sequence_index_owner,
)
from core.errors.exceptions import ValidationError
from core.tool_calls.status_values import TOOL_CALL_PERSISTED_STATUSES
from core.validation.record_fields import require_bool, require_int, require_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("validate_assistant_event_timeline",)


def _validate_payload_identity(
    payload_value: dict[str, JSONValue],
    *,
    message_index: int,
    expected_sequence: int,
    expected_revision: int,
    assistant_at_ms: int | None,
) -> None:
    payload_revision_value = payload_value.get("assistant_revision")
    if payload_revision_value is not None:
        if (
            isinstance(payload_revision_value, bool)
            or not isinstance(payload_revision_value, int)
            or payload_revision_value != expected_revision
        ):
            raise ValidationError(
                "assistant_event_timeline.payload.assistant_revision must equal assistant_revision.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload.assistant_revision",
                },
            )
    if assistant_at_ms is None:
        return
    payload_assistant_at_ms = payload_value.get("assistant_at_ms")
    if payload_assistant_at_ms is None:
        return
    if (
        isinstance(payload_assistant_at_ms, bool)
        or not isinstance(payload_assistant_at_ms, int)
        or payload_assistant_at_ms != assistant_at_ms
    ):
        raise ValidationError(
            "assistant_event_timeline.payload.assistant_at_ms must equal the assistant message timestamp.",
            details={
                "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload.assistant_at_ms",
            },
        )


def _timeline_field_error(message: str, *, param: str) -> ValidationError:
    return ValidationError(message, details={"param": param})


def _raise_tool_payload_error(*, message: str, param: str) -> NoReturn:
    raise _timeline_field_error(message, param=param)


def _validate_tool_payload_contract(
    tool_value: dict[str, JSONValue],
    *,
    message_index: int,
    expected_sequence: int,
) -> tuple[str, int]:
    tool_param = (
        f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload.tool"
    )
    call_id = require_non_empty_str(
        tool_value.get("call_id"),
        label="tool.call_id",
        build_error=partial(_timeline_field_error, param=f"{tool_param}.call_id"),
        invalid_message="assistant_event_timeline.tool.call_id must be a non-empty string.",
    )
    require_non_empty_str(
        tool_value.get("tool_name"),
        label="tool.tool_name",
        build_error=partial(_timeline_field_error, param=f"{tool_param}.tool_name"),
        invalid_message="assistant_event_timeline.tool.tool_name must be a non-empty string.",
    )
    status = require_non_empty_str(
        tool_value.get("status"),
        label="tool.status",
        build_error=partial(_timeline_field_error, param=f"{tool_param}.status"),
        invalid_message="assistant_event_timeline.tool.status must be a non-empty string.",
    )
    if status not in TOOL_CALL_PERSISTED_STATUSES:
        _raise_tool_payload_error(
            message="assistant_event_timeline.tool.status is invalid.",
            param=f"{tool_param}.status",
        )
    sequence_index = require_int(
        tool_value.get("sequence_index"),
        label="tool.sequence_index",
        build_error=partial(_timeline_field_error, param=f"{tool_param}.sequence_index"),
        minimum=0,
        invalid_message=(
            "assistant_event_timeline.tool.sequence_index must be a non-negative integer."
        ),
    )
    require_int(
        tool_value.get("message_index"),
        label="tool.message_index",
        build_error=partial(_timeline_field_error, param=f"{tool_param}.message_index"),
        minimum=0,
        invalid_message=(
            "assistant_event_timeline.tool.message_index must be a non-negative integer."
        ),
    )
    require_int(
        tool_value.get("content_index_before"),
        label="tool.content_index_before",
        build_error=partial(
            _timeline_field_error,
            param=f"{tool_param}.content_index_before",
        ),
        minimum=0,
        invalid_message=(
            "assistant_event_timeline.tool.content_index_before must be a non-negative integer."
        ),
    )
    require_int(
        tool_value.get("thinking_index_before"),
        label="tool.thinking_index_before",
        build_error=partial(
            _timeline_field_error,
            param=f"{tool_param}.thinking_index_before",
        ),
        minimum=0,
        invalid_message=(
            "assistant_event_timeline.tool.thinking_index_before must be a non-negative integer."
        ),
    )
    require_bool(
        tool_value.get("collapsed"),
        label="tool.collapsed",
        build_error=partial(_timeline_field_error, param=f"{tool_param}.collapsed"),
        invalid_message="assistant_event_timeline.tool.collapsed must be a boolean.",
    )
    return (call_id, sequence_index)


def validate_assistant_event_timeline(
    value: JSONValue,
    *,
    message_index: int,
    assistant_at_ms: int | None = None,
) -> set[str]:
    if not isinstance(value, list):
        raise ValidationError(
            "assistant_event_timeline must be an array.",
            details={"param": f"messages[{message_index}].assistant_event_timeline"},
        )
    sequence_owner_by_sequence_index: dict[int, str] = {}
    call_owner_by_call_id: dict[str, int] = {}
    completed_call_ids: set[str] = set()
    for expected_sequence, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ValidationError(
                "assistant_event_timeline entry must be an object.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}]",
                },
            )
        sequence_value = entry.get("sequence")
        if (
            isinstance(sequence_value, bool)
            or not isinstance(sequence_value, int)
            or sequence_value < 0
        ):
            raise ValidationError(
                "assistant_event_timeline.sequence must be a non-negative integer.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].sequence",
                },
            )
        if sequence_value != expected_sequence:
            raise ValidationError(
                "assistant_event_timeline sequence must be contiguous starting at 0.",
                details={"param": f"messages[{message_index}].assistant_event_timeline"},
            )
        revision_value = entry.get("assistant_revision")
        if (
            isinstance(revision_value, bool)
            or not isinstance(revision_value, int)
            or revision_value <= 0
        ):
            raise ValidationError(
                "assistant_event_timeline.assistant_revision must be a positive integer.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].assistant_revision",
                },
            )
        if revision_value != sequence_value + 1:
            raise ValidationError(
                "assistant_event_timeline.assistant_revision must equal sequence + 1.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].assistant_revision",
                },
            )
        event_type_value = entry.get("event_type")
        if not isinstance(event_type_value, str) or not event_type_value.strip():
            raise ValidationError(
                "assistant_event_timeline.event_type must be a non-empty string.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].event_type",
                },
            )
        event_type = event_type_value.strip()
        if event_type == "tool_call_output_delta":
            raise ValidationError(
                "assistant_event_timeline tool_call_output_delta is not a supported timeline event.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].event_type",
                },
            )
        payload_value = entry.get("payload")
        if not isinstance(payload_value, dict):
            raise ValidationError(
                "assistant_event_timeline.payload must be a JSON object.",
                details={
                    "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload",
                },
            )
        _validate_payload_identity(
            payload_value,
            message_index=message_index,
            expected_sequence=expected_sequence,
            expected_revision=revision_value,
            assistant_at_ms=assistant_at_ms,
        )
        if event_type == "thinking_phase":
            thinking_value = payload_value.get("thinking_phase")
            if not isinstance(thinking_value, dict):
                raise ValidationError(
                    "assistant_event_timeline thinking_phase events require a thinking_phase payload object.",
                    details={
                        "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload.thinking_phase",
                    },
                )
            validate_thinking_phase_payload_contract(
                thinking_value,
                message_index=message_index,
                expected_sequence=expected_sequence,
            )
            continue
        tool_value = payload_value.get("tool")
        if not isinstance(tool_value, dict):
            if event_type.startswith("tool_call_"):
                raise ValidationError(
                    "assistant_event_timeline tool events require a tool payload object.",
                    details={
                        "param": f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload.tool",
                    },
                )
            continue
        call_id, sequence_index = _validate_tool_payload_contract(
            tool_value,
            message_index=message_index,
            expected_sequence=expected_sequence,
        )
        register_tool_call_sequence_index_owner(
            sequence_owner_by_sequence_index=sequence_owner_by_sequence_index,
            call_owner_by_call_id=call_owner_by_call_id,
            sequence_index=sequence_index,
            call_id=call_id,
            source="assistant_event_timeline",
        )
        if event_type == "tool_call_completed":
            if call_id in completed_call_ids:
                raise ValidationError(
                    "assistant_event_timeline contains duplicate completed tool events for the same call_id.",
                )
            completed_call_ids.add(call_id)
    return completed_call_ids
