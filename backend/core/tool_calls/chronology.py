"""SoAI - Tool call chronology field validation [backend/core/tool_calls/chronology.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import is_non_negative_strict_int
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ToolCallChronologyFields",
    "bound_optional_chronology_anchor",
    "bound_required_chronology_anchor",
    "offset_required_chronology_anchor",
    "resolve_content_index_before",
    "resolve_explicit_call_chronology",
    "resolve_optional_non_negative_integer",
    "resolve_optional_thinking_duration_before_ms",
    "resolve_required_non_negative_integer",
    "resolve_sequence_index",
    "resolve_thinking_index_before",
    "resolve_tool_call_chronology_fields",
)


@dataclass(frozen=True, slots=True)
class ToolCallChronologyFields:
    sequence_index: int
    content_index_before: int
    thinking_index_before: int
    thinking_duration_before_ms: int | None = None


def _resolve_non_negative_integer(
    value: JSONValue | None,
    field_name: str,
    *,
    field_label: str = "Tool call",
    required: bool = False,
    exception_type: type[Exception] = ValidationError,
    required_message: str | None = None,
) -> int | None:
    coerced = coerce_optional_non_negative_int_strict(value)
    if coerced is not None:
        return coerced
    if value is None:
        if required:
            message = required_message or (f"{field_label} field '{field_name}' is required.")
            raise exception_type(message)
        return None
    if required:
        raise exception_type(f"{field_label} field '{field_name}' must be a non-negative integer.")
    raise exception_type(
        f"{field_label} field '{field_name}' must be a non-negative integer when provided.",
    )


def resolve_required_non_negative_integer(
    value: JSONValue | None,
    field_name: str,
    *,
    field_label: str = "Tool call",
    exception_type: type[Exception] = ValidationError,
    required_message: str | None = None,
) -> int:
    resolved = _resolve_non_negative_integer(
        value,
        field_name,
        field_label=field_label,
        required=True,
        exception_type=exception_type,
        required_message=required_message,
    )
    if resolved is None:
        raise exception_type(required_message or f"{field_label} field '{field_name}' is required.")
    return resolved


def resolve_optional_non_negative_integer(
    value: JSONValue | None,
    field_name: str,
    *,
    field_label: str = "Tool call",
    exception_type: type[Exception] = ValidationError,
) -> int | None:
    return _resolve_non_negative_integer(
        value,
        field_name,
        field_label=field_label,
        required=False,
        exception_type=exception_type,
    )


def _require_internal_non_negative_integer(
    value: int,
    field_name: str,
    *,
    field_label: str,
    exception_type: type[Exception],
) -> int:
    if not is_non_negative_strict_int(value):
        raise exception_type(f"{field_label} {field_name} must be a non-negative integer.")
    return value


def bound_required_chronology_anchor(
    value: JSONValue | None,
    field_name: str,
    *,
    upper_bound: int,
    field_label: str = "Tool call",
    exception_type: type[Exception] = ValidationError,
    required_message: str | None = None,
) -> int:
    resolved = resolve_required_non_negative_integer(
        value,
        field_name,
        field_label=field_label,
        exception_type=exception_type,
        required_message=required_message,
    )
    boundary = _require_internal_non_negative_integer(
        upper_bound,
        "upper_bound",
        field_label=field_label,
        exception_type=exception_type,
    )
    return min(resolved, boundary)


def bound_optional_chronology_anchor(
    value: JSONValue | None,
    field_name: str,
    *,
    upper_bound: int,
    field_label: str = "Tool call",
    exception_type: type[Exception] = ValidationError,
) -> int:
    resolved = resolve_optional_non_negative_integer(
        value,
        field_name,
        field_label=field_label,
        exception_type=exception_type,
    )
    boundary = _require_internal_non_negative_integer(
        upper_bound,
        "upper_bound",
        field_label=field_label,
        exception_type=exception_type,
    )
    if resolved is None:
        return boundary
    return min(resolved, boundary)


def offset_required_chronology_anchor(
    value: JSONValue | None,
    field_name: str,
    *,
    offset: int,
    upper_bound: int | None = None,
    field_label: str = "Tool call",
    exception_type: type[Exception] = ValidationError,
    required_message: str | None = None,
) -> int:
    resolved = resolve_required_non_negative_integer(
        value,
        field_name,
        field_label=field_label,
        exception_type=exception_type,
        required_message=required_message,
    )
    resolved_offset = _require_internal_non_negative_integer(
        offset,
        "offset",
        field_label=field_label,
        exception_type=exception_type,
    )
    shifted = resolved + resolved_offset
    if upper_bound is None:
        return shifted
    boundary = _require_internal_non_negative_integer(
        upper_bound,
        "upper_bound",
        field_label=field_label,
        exception_type=exception_type,
    )
    return min(shifted, boundary)


def resolve_sequence_index(call: JSONDict) -> int:
    return resolve_required_non_negative_integer(
        call.get("sequence_index"),
        "sequence_index",
        required_message="Tool call field 'sequence_index' is required.",
    )


def resolve_content_index_before(call: JSONDict) -> int:
    return resolve_required_non_negative_integer(
        call.get("content_index_before"),
        "content_index_before",
        required_message="Tool call field 'content_index_before' is required.",
    )


def resolve_thinking_index_before(call: JSONDict) -> int:
    return resolve_required_non_negative_integer(
        call.get("thinking_index_before"),
        "thinking_index_before",
        required_message="Tool call field 'thinking_index_before' is required.",
    )


def resolve_optional_thinking_duration_before_ms(call: JSONDict) -> int | None:
    return resolve_optional_non_negative_integer(
        call.get("thinking_duration_before_ms"),
        "thinking_duration_before_ms",
    )


def resolve_tool_call_chronology_fields(
    call: JSONDict,
    *,
    field_label: str = "Tool call",
) -> ToolCallChronologyFields:
    return ToolCallChronologyFields(
        sequence_index=resolve_required_non_negative_integer(
            call.get("sequence_index"),
            "sequence_index",
            field_label=field_label,
            required_message=f"{field_label} field 'sequence_index' is required.",
        ),
        content_index_before=resolve_required_non_negative_integer(
            call.get("content_index_before"),
            "content_index_before",
            field_label=field_label,
            required_message=f"{field_label} field 'content_index_before' is required.",
        ),
        thinking_index_before=resolve_required_non_negative_integer(
            call.get("thinking_index_before"),
            "thinking_index_before",
            field_label=field_label,
            required_message=f"{field_label} field 'thinking_index_before' is required.",
        ),
        thinking_duration_before_ms=resolve_optional_non_negative_integer(
            call.get("thinking_duration_before_ms"),
            "thinking_duration_before_ms",
            field_label=field_label,
        ),
    )


def resolve_explicit_call_chronology(call: JSONDict) -> tuple[int, int, int] | None:
    has_sequence_index = "sequence_index" in call
    has_content_index_before = "content_index_before" in call
    has_thinking_index_before = "thinking_index_before" in call
    has_any_chronology_field = (
        has_sequence_index or has_content_index_before or has_thinking_index_before
    )
    if not has_any_chronology_field:
        return None
    if not (has_sequence_index and has_content_index_before and has_thinking_index_before):
        raise ValidationError(
            "Tool call chronology fields must include sequence_index, content_index_before, and thinking_index_before together.",
        )
    sequence_index = resolve_sequence_index(call)
    content_index_before = resolve_content_index_before(call)
    thinking_index_before = resolve_thinking_index_before(call)
    return (sequence_index, content_index_before, thinking_index_before)
