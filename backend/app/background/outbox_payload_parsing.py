"""SoAI - Canonical outbox payload parsing primitives [backend/app/background/outbox_payload_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.serialization.json_parsing import parse_json_dict_with_messages
from core.types.json import JSONValue
from core.types.json_value import coerce_str_list
from core.validation.numbers import coerce_float_from_json
from core.validation.record_fields import (
    require_bool,
    require_int,
    require_non_empty_str,
)

__all__ = (
    "coerce_outbox_bool",
    "coerce_outbox_int",
    "coerce_outbox_optional_str",
    "coerce_outbox_str",
    "coerce_outbox_str_tuple",
    "parse_outbox_payload_object",
    "require_positive_outbox_timestamp_seconds",
)


def coerce_outbox_int(value: JSONValue, *, label: str) -> int:
    return require_int(
        value,
        label=label,
        build_error=ValidationError,
        invalid_message=f"{label} must be an integer.",
    )


def coerce_outbox_bool(value: JSONValue, *, label: str) -> bool:
    return require_bool(
        value,
        label=label,
        build_error=ValidationError,
        invalid_message=f"{label} must be a boolean.",
    )


def coerce_outbox_str(value: JSONValue, *, label: str) -> str:
    try:
        return require_non_empty_str(value, label=label, build_error=ValidationError)
    except ValidationError as exception:
        raise ValidationError(f"{label} must be a string.") from exception


def coerce_outbox_optional_str(value: JSONValue, *, label: str) -> str | None:
    if value is None:
        return None
    return coerce_outbox_str(value, label=label)


def coerce_outbox_str_tuple(value: JSONValue, *, label: str) -> tuple[str, ...]:
    items = coerce_str_list(value)
    if items is None or any(not item or item != item.strip() for item in items):
        raise ValidationError(f"{label} must be an array of non-empty strings.")
    if len(set(items)) != len(items):
        raise ValidationError(f"{label} must not contain duplicate strings.")
    return tuple(items)


def parse_outbox_payload_object(payload_json: str) -> dict[str, JSONValue]:
    return parse_json_dict_with_messages(
        payload_json,
        field="Outbox payload",
        invalid_json_message="Outbox payload is not valid JSON.",
        invalid_object_message="Outbox payload must be a JSON object.",
    )


def require_positive_outbox_timestamp_seconds(value: JSONValue, *, error_message: str) -> float:
    parsed = coerce_float_from_json(
        value,
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )
    if parsed is None or parsed <= 0.0:
        raise ValidationError(error_message)
    return parsed
