"""SoAI - Assistant timeline thinking phase payload validation [backend/core/assistant_timeline/thinking_payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, NoReturn

from core.errors.exceptions import ValidationError
from core.validation.record_fields import require_bool, require_int, require_non_empty_str

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("validate_thinking_phase_payload_contract",)

_THINKING_RENDER_MODES: frozenset[str] = frozenset(
    ("preface_only", "preface_and_thinking", "thinking_only"),
)
_THINKING_STATUSES: frozenset[str] = frozenset(("running", "completed", "cancelled", "error"))
_THINKING_ANCHOR_TYPES: frozenset[str] = frozenset(("before_call", "after_call", "position"))


def _thinking_field_error(message: str, *, param: str) -> ValidationError:
    return ValidationError(message, details={"param": param})


def _raise_thinking_payload_error(*, message: str, param: str) -> NoReturn:
    raise _thinking_field_error(message, param=param)


def validate_thinking_phase_payload_contract(
    thinking_value: dict[str, JSONValue],
    *,
    message_index: int,
    expected_sequence: int,
) -> tuple[str, int]:
    thinking_param = f"messages[{message_index}].assistant_event_timeline[{expected_sequence}].payload.thinking_phase"
    phase_id = require_non_empty_str(
        thinking_value.get("phase_id"),
        label="thinking_phase.phase_id",
        build_error=partial(_thinking_field_error, param=f"{thinking_param}.phase_id"),
        invalid_message=(
            "assistant_event_timeline.thinking_phase.phase_id must be a non-empty string."
        ),
    )
    sequence_index = require_int(
        thinking_value.get("sequence_index"),
        label="thinking_phase.sequence_index",
        build_error=partial(
            _thinking_field_error,
            param=f"{thinking_param}.sequence_index",
        ),
        minimum=0,
        invalid_message=(
            "assistant_event_timeline.thinking_phase.sequence_index must be a non-negative integer."
        ),
    )
    anchor_type = require_non_empty_str(
        thinking_value.get("anchor_type"),
        label="thinking_phase.anchor_type",
        build_error=partial(_thinking_field_error, param=f"{thinking_param}.anchor_type"),
        invalid_message=(
            "assistant_event_timeline.thinking_phase.anchor_type must be a non-empty string."
        ),
    )
    if anchor_type not in _THINKING_ANCHOR_TYPES:
        _raise_thinking_payload_error(
            message="assistant_event_timeline.thinking_phase.anchor_type is invalid.",
            param=f"{thinking_param}.anchor_type",
        )
    require_non_empty_str(
        thinking_value.get("text"),
        label="thinking_phase.text",
        build_error=partial(_thinking_field_error, param=f"{thinking_param}.text"),
        invalid_message=(
            "assistant_event_timeline.thinking_phase.text must be a non-empty string."
        ),
    )
    render_mode = require_non_empty_str(
        thinking_value.get("render_mode"),
        label="thinking_phase.render_mode",
        build_error=partial(_thinking_field_error, param=f"{thinking_param}.render_mode"),
        invalid_message=(
            "assistant_event_timeline.thinking_phase.render_mode must be a non-empty string."
        ),
    )
    if render_mode not in _THINKING_RENDER_MODES:
        _raise_thinking_payload_error(
            message="assistant_event_timeline.thinking_phase.render_mode is invalid.",
            param=f"{thinking_param}.render_mode",
        )
    preface_complete = require_bool(
        thinking_value.get("preface_complete"),
        label="thinking_phase.preface_complete",
        build_error=partial(
            _thinking_field_error,
            param=f"{thinking_param}.preface_complete",
        ),
        invalid_message=(
            "assistant_event_timeline.thinking_phase.preface_complete must be a boolean."
        ),
    )
    status = require_non_empty_str(
        thinking_value.get("status"),
        label="thinking_phase.status",
        build_error=partial(_thinking_field_error, param=f"{thinking_param}.status"),
        invalid_message=(
            "assistant_event_timeline.thinking_phase.status must be a non-empty string."
        ),
    )
    if status not in _THINKING_STATUSES:
        _raise_thinking_payload_error(
            message="assistant_event_timeline.thinking_phase.status is invalid.",
            param=f"{thinking_param}.status",
        )
    require_bool(
        thinking_value.get("collapsed"),
        label="thinking_phase.collapsed",
        build_error=partial(_thinking_field_error, param=f"{thinking_param}.collapsed"),
        invalid_message="assistant_event_timeline.thinking_phase.collapsed must be a boolean.",
    )
    if anchor_type == "position":
        require_int(
            thinking_value.get("anchor_position"),
            label="thinking_phase.anchor_position",
            build_error=partial(
                _thinking_field_error,
                param=f"{thinking_param}.anchor_position",
            ),
            minimum=0,
            invalid_message=(
                "assistant_event_timeline.thinking_phase.anchor_position must be a non-negative integer."
            ),
        )
        if "anchor_call_id" in thinking_value:
            _raise_thinking_payload_error(
                message="assistant_event_timeline.thinking_phase.anchor_call_id is invalid for position anchors.",
                param=f"{thinking_param}.anchor_call_id",
            )
    else:
        require_non_empty_str(
            thinking_value.get("anchor_call_id"),
            label="thinking_phase.anchor_call_id",
            build_error=partial(
                _thinking_field_error,
                param=f"{thinking_param}.anchor_call_id",
            ),
            invalid_message=(
                "assistant_event_timeline.thinking_phase.anchor_call_id must be a non-empty string."
            ),
        )
        if "anchor_position" in thinking_value:
            _raise_thinking_payload_error(
                message="assistant_event_timeline.thinking_phase.anchor_position is invalid for tool anchors.",
                param=f"{thinking_param}.anchor_position",
            )
    preface_text = thinking_value.get("preface_text")
    if render_mode == "thinking_only":
        if preface_complete:
            _raise_thinking_payload_error(
                message="assistant_event_timeline.thinking_phase.thinking_only must not complete a preface.",
                param=f"{thinking_param}.preface_complete",
            )
        if preface_text is not None:
            _raise_thinking_payload_error(
                message="assistant_event_timeline.thinking_phase.thinking_only must not include preface_text.",
                param=f"{thinking_param}.preface_text",
            )
    else:
        require_non_empty_str(
            thinking_value.get("preface_text"),
            label="thinking_phase.preface_text",
            build_error=partial(
                _thinking_field_error,
                param=f"{thinking_param}.preface_text",
            ),
            invalid_message=(
                "assistant_event_timeline.thinking_phase.preface_text must be a non-empty string."
            ),
        )
    if "duration_ms" in thinking_value:
        require_int(
            thinking_value.get("duration_ms"),
            label="thinking_phase.duration_ms",
            build_error=partial(
                _thinking_field_error,
                param=f"{thinking_param}.duration_ms",
            ),
            minimum=0,
            invalid_message=(
                "assistant_event_timeline.thinking_phase.duration_ms must be a non-negative integer."
            ),
        )
    if "started_at_ms" in thinking_value:
        require_int(
            thinking_value.get("started_at_ms"),
            label="thinking_phase.started_at_ms",
            build_error=partial(
                _thinking_field_error,
                param=f"{thinking_param}.started_at_ms",
            ),
            minimum=0,
            invalid_message=(
                "assistant_event_timeline.thinking_phase.started_at_ms must be a non-negative integer."
            ),
        )
    return phase_id, sequence_index
