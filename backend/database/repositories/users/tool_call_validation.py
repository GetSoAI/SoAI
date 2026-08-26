"""SoAI - Tool call repository validation helpers [backend/database/repositories/users/tool_call_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.tool_calls.chronology import (
    resolve_optional_non_negative_integer,
    resolve_required_non_negative_integer,
)
from core.tool_calls.status_values import (
    TOOL_CALL_FAILURE_STATUSES,
    TOOL_CALL_PERSISTED_STATUSES,
    TOOL_CALL_TERMINAL_STATUSES,
)
from core.validation.epoch import require_unix_epoch_ms
from core.validation.record_fields import (
    require_bool,
    require_non_empty_str,
    require_optional_str,
)
from database.core.json_codec import parse_optional_json_string_field

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "ValidatedToolCallWriteFields",
    "parse_optional_json_from_row",
    "require_non_empty_string_from_row",
    "require_non_negative_integer_from_row",
    "require_optional_non_negative_integer_from_row",
    "resolve_tool_call_sequence_index",
    "validate_collapsed_value",
    "validate_non_negative_integer",
    "validate_optional_epoch_ms_integer",
    "validate_optional_string",
    "validate_required_epoch_ms_integer",
    "validate_status",
    "validate_status_completed_at_ms_pair",
    "validate_terminal_status_error_message",
    "validate_tool_call_write_fields",
)

LOGGER_NAME = "SoAI.database.repositories.tool_call_validation"


_VALID_TOOL_CALL_STATUSES: frozenset[str] = TOOL_CALL_PERSISTED_STATUSES


@dataclass(frozen=True, slots=True)
class ValidatedToolCallWriteFields:
    status: str | None
    error_message: str | None
    duration_ms: int | None
    started_at_ms: int | None
    completed_at_ms: int | None


def validate_non_negative_integer(value: JSONValue | None, field_name: str) -> int | None:
    return resolve_optional_non_negative_integer(
        value,
        field_name,
        field_label="Tool call",
        exception_type=ValidationError,
    )


def validate_optional_epoch_ms_integer(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    require_unix_epoch_ms(
        value,
        error_message=f"Tool call field '{field_name}' must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    return value


def validate_required_epoch_ms_integer(value: int, field_name: str) -> int:
    require_unix_epoch_ms(
        value,
        error_message=f"Tool call field '{field_name}' must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    return value


def validate_collapsed_value(collapsed: bool | None) -> int:
    validated = require_bool(
        collapsed,
        label="collapsed",
        build_error=ValidationError,
        invalid_message="Tool call field 'collapsed' must be a boolean.",
    )
    return 1 if validated else 0


def validate_optional_string(value: JSONValue | None, field_name: str) -> str | None:
    return require_optional_str(
        value,
        label=field_name,
        build_error=ValidationError,
        invalid_message=f"Tool call field '{field_name}' must be a string when provided.",
    )


def validate_status(status: str, *, operation: str, call_id: str) -> str:
    if status not in _VALID_TOOL_CALL_STATUSES:
        logger = get_logger(LOGGER_NAME)
        logger.error(
            "Invalid tool call status %r for call_id=%r (%s). Valid: %s",
            status,
            call_id,
            operation,
            sorted(_VALID_TOOL_CALL_STATUSES),
            stack_info=True,
        )
        raise ValidationError(
            f"Invalid tool call status {status!r}. Allowed: {', '.join(sorted(_VALID_TOOL_CALL_STATUSES))}",
        )
    return status


def validate_terminal_status_error_message(
    status: str | None,
    error_message: str | None,
    *,
    operation: str,
    call_id: str,
) -> str | None:
    if status not in TOOL_CALL_FAILURE_STATUSES:
        return error_message
    if isinstance(error_message, str) and error_message.strip():
        return error_message.strip()
    raise ValidationError(
        f"Tool call {operation} for call_id={call_id!r} requires a non-empty error_message when status is {status!r}.",
    )


def validate_status_completed_at_ms_pair(
    status: str | None,
    completed_at_ms: int | None,
    *,
    operation: str,
    call_id: str,
) -> None:
    if status is None:
        if completed_at_ms is not None:
            raise ValidationError(
                f"Tool call {operation} for call_id={call_id!r} requires status when setting completed_at_ms.",
            )
        return
    if status in TOOL_CALL_TERMINAL_STATUSES:
        if completed_at_ms is None:
            raise ValidationError(
                f"Tool call {operation} for call_id={call_id!r} requires completed_at_ms when status is {status!r}.",
            )
        return
    if completed_at_ms is not None:
        raise ValidationError(
            f"Tool call {operation} for call_id={call_id!r} must not set completed_at_ms when status is {status!r}.",
        )


def validate_tool_call_write_fields(
    *,
    status: str | None,
    error_message: JSONValue | None,
    duration_ms: JSONValue | None,
    started_at_ms: int | None,
    completed_at_ms: int | None,
    operation: str,
    call_id: str,
) -> ValidatedToolCallWriteFields:
    validated_status = (
        validate_status(status, operation=operation, call_id=call_id)
        if status is not None
        else None
    )
    validated_error_message = validate_optional_string(error_message, "error_message")
    validated_error_message = validate_terminal_status_error_message(
        validated_status,
        validated_error_message,
        operation=operation,
        call_id=call_id,
    )
    validated_duration_ms = validate_non_negative_integer(duration_ms, "duration_ms")
    validated_started_at_ms = validate_optional_epoch_ms_integer(
        started_at_ms,
        "started_at_ms",
    )
    validated_completed_at_ms = validate_optional_epoch_ms_integer(
        completed_at_ms,
        "completed_at_ms",
    )
    validate_status_completed_at_ms_pair(
        validated_status,
        validated_completed_at_ms,
        operation=operation,
        call_id=call_id,
    )
    return ValidatedToolCallWriteFields(
        status=validated_status,
        error_message=validated_error_message,
        duration_ms=validated_duration_ms,
        started_at_ms=validated_started_at_ms,
        completed_at_ms=validated_completed_at_ms,
    )


def require_non_negative_integer_from_row(value: JSONValue | None, field_name: str) -> int:
    return resolve_required_non_negative_integer(
        value,
        field_name,
        field_label="Tool call",
        exception_type=ValidationError,
    )


def require_optional_non_negative_integer_from_row(
    value: JSONValue | None,
    field_name: str,
) -> int | None:
    return validate_non_negative_integer(value, field_name)


def require_non_empty_string_from_row(value: JSONValue | None, field_name: str) -> str:
    return require_non_empty_str(
        value,
        label=field_name,
        build_error=ValidationError,
        invalid_message=f"Tool call field '{field_name}' must be a non-empty string.",
    )


def parse_optional_json_from_row(value: JSONValue | None, field_name: str) -> JSONValue | None:
    return parse_optional_json_string_field(
        value,
        type_message=f"Tool call field '{field_name}' must be a JSON string when provided.",
        invalid_message=f"Tool call field '{field_name}' must contain valid JSON.",
        json_value_message=(
            f"Tool call field '{field_name}' must contain a JSON-serializable value."
        ),
    )


def resolve_tool_call_sequence_index(provided_sequence_index: int | None) -> int:
    return resolve_required_non_negative_integer(
        provided_sequence_index,
        "sequence_index",
        field_label="Tool call",
        exception_type=ValidationError,
        required_message="Tool call field 'sequence_index' is required.",
    )
