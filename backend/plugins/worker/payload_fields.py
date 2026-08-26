"""SoAI - Plugin worker payload field readers [backend/plugins/worker/payload_fields.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.argument_numbers import require_scalar_value
from core.mcp.argument_validation import require_non_empty_string_value
from core.validation.record_fields import (
    require_bool,
    require_int,
    require_json_object,
    require_json_object_list,
    require_number,
    require_optional_json_object,
    require_str_list,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "read_bool_field",
    "read_dict_field",
    "read_dict_list_field",
    "read_int_field",
    "read_non_empty_raw_str_field",
    "read_non_empty_str_field",
    "read_number_field",
    "read_optional_dict_field",
    "read_optional_int_field",
    "read_optional_str_field",
    "read_required_int_field",
    "read_required_named_str_field",
    "read_required_str_field",
    "read_scalar_field",
    "read_str_field",
    "read_str_list_field",
    "read_worker_request_str_field",
)

WORKER_REQUEST_FIELD_LABEL = "Worker request field"


def read_str_field(payload: JSONDict, key: str, *, label: str) -> str:
    value: JSONValue | None = payload.get(key)
    if not isinstance(value, str):
        raise ValidationError(f"{label} '{key}' must be a string.")
    return value


def read_non_empty_str_field(payload: JSONDict, key: str, *, label: str) -> str:
    return require_non_empty_string_value(
        payload.get(key),
        build_error=ValidationError,
        type_message=f"{label} '{key}' must be a string.",
        empty_message=f"{label} '{key}' must be a non-empty string.",
    )


def read_non_empty_raw_str_field(
    payload: JSONDict,
    key: str,
    *,
    label: str,
    empty_message: str | None = None,
) -> str:
    value: JSONValue | None = payload.get(key)
    if not isinstance(value, str):
        raise ValidationError(f"{label} '{key}' must be a string.")
    if not value:
        raise ValidationError(empty_message or f"{label} '{key}' must be a string.")
    return value


def read_required_str_field(
    payload: JSONDict,
    key: str,
    *,
    missing_message: str,
    type_message: str,
    empty_message: str,
) -> str:
    value: JSONValue | None = payload.get(key)
    if value is None:
        raise ValidationError(missing_message)
    return require_non_empty_string_value(
        value,
        build_error=ValidationError,
        type_message=type_message,
        empty_message=empty_message,
    )


def read_required_named_str_field(payload: JSONDict, key: str, *, label: str) -> str:
    return read_required_str_field(
        payload,
        key,
        missing_message=f"{label} '{key}' is required.",
        type_message=f"{label} '{key}' must be a string.",
        empty_message=f"{label} '{key}' is required.",
    )


def read_worker_request_str_field(payload: JSONDict, key: str) -> str:
    return read_non_empty_raw_str_field(
        payload,
        key,
        label=WORKER_REQUEST_FIELD_LABEL,
        empty_message=f"{WORKER_REQUEST_FIELD_LABEL} '{key}' must be a non-empty string.",
    )


def read_optional_str_field(
    payload: JSONDict,
    key: str,
    *,
    label: str,
) -> str | None:
    value: JSONValue | None = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{label} '{key}' must be a string.")
    return value


def read_bool_field(payload: JSONDict, key: str, *, label: str) -> bool:
    return require_bool(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be a boolean.",
    )


def read_int_field(payload: JSONDict, key: str, *, label: str, default: int) -> int:
    value: JSONValue | None = payload.get(key)
    if value is None:
        return default
    return require_int(
        value,
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be an integer.",
    )


def read_required_int_field(payload: JSONDict, key: str, *, label: str) -> int:
    return require_int(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be an integer.",
    )


def read_optional_int_field(payload: JSONDict, key: str, *, label: str) -> int | None:
    value: JSONValue | None = payload.get(key)
    if value is None:
        return None
    return require_int(
        value,
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be an integer.",
    )


def read_number_field(payload: JSONDict, key: str, *, label: str) -> int | float:
    return require_number(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be a number.",
        finite_message=f"{label} '{key}' must be a finite number.",
    )


def read_scalar_field(payload: JSONDict, key: str, *, label: str) -> str | int | float:
    return require_scalar_value(
        payload.get(key),
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be a scalar.",
        finite_message=f"{label} '{key}' must be a finite scalar.",
    )


def read_dict_field(payload: JSONDict, key: str, *, label: str) -> JSONDict:
    return require_json_object(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be a JSON object.",
    )


def read_optional_dict_field(payload: JSONDict, key: str, *, label: str) -> JSONDict | None:
    return require_optional_json_object(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be a JSON object.",
    )


def read_str_list_field(payload: JSONDict, key: str, *, label: str) -> list[str]:
    return require_str_list(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        allow_empty=True,
        strip_items=False,
        reject_empty_items=False,
        invalid_message=f"{label} '{key}' must be a string list.",
        entry_message=f"{label} '{key}' must contain only strings.",
    )


def read_dict_list_field(payload: JSONDict, key: str, *, label: str) -> list[JSONDict]:
    return require_json_object_list(
        payload.get(key),
        label=f"{label} '{key}'",
        build_error=ValidationError,
        invalid_message=f"{label} '{key}' must be a JSON object list.",
        entry_message=f"{label} '{key}' must contain only JSON objects.",
    )
