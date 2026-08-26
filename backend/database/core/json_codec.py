"""SoAI - Database JSON serialization helpers [backend/database/core/json_codec.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.types.json import is_json_dict, is_json_list, is_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRow, SQLiteValue

__all__ = (
    "coerce_optional_json_from_sqlite",
    "coerce_optional_json_from_sqlite_row",
    "parse_optional_json_list_field",
    "parse_optional_json_object_field",
    "parse_optional_json_string_field",
    "safe_json_deserialize",
    "safe_json_deserialize_required_list",
    "safe_json_deserialize_required_object",
    "safe_json_serialize",
    "safe_json_serialize_value",
    "serialize_optional_json_list_field",
    "serialize_optional_json_object_field",
    "serialize_required_json_list_field",
    "serialize_required_json_object_field",
)


def safe_json_serialize(
    value: JSONValue,
    field_name: str = "unknown",
    identifier: str = "unknown",
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_json_value(value)
        if not is_json_value(parsed):
            raise ValidationError(
                f"Field '{field_name}' for '{identifier}' must be JSON-compatible.",
                details={"field_name": field_name, "identifier": identifier},
            )
        return value
    try:
        return serialize_json_compact_stable_strict(value)
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            f"Failed to serialize '{field_name}' for '{identifier}'.",
            details={"field_name": field_name, "identifier": identifier},
            cause=exception,
        ) from exception


def safe_json_serialize_value(
    value: JSONValue,
    *,
    field_name: str,
    identifier: str,
) -> str:
    try:
        return serialize_json_compact_stable_strict(value)
    except (TypeError, ValueError) as exception:
        raise ValidationError(
            f"Failed to serialize '{field_name}' for '{identifier}'.",
            details={"field_name": field_name, "identifier": identifier},
            cause=exception,
        ) from exception


def safe_json_deserialize(
    value: SQLiteValue | JSONValue,
    default: JSONValue | None = None,
) -> JSONValue | None:
    if value is None:
        return default
    if isinstance(value, bytes | bytearray | memoryview):
        raise ValidationError(
            "Database JSON field cannot be binary.",
            details={"value_type": type(value).__name__},
        )
    if isinstance(value, str):
        parsed = parse_json_value(value)
        if not is_json_value(parsed):
            raise ValidationError(
                "Database JSON field is not JSON-compatible.",
                details={"value_type": type(parsed).__name__},
            )
        return parsed
    if is_json_value(value):
        return value
    raise ValidationError(
        "Database JSON field is not JSON-compatible.",
        details={"value_type": type(value).__name__},
    )


def safe_json_deserialize_required_object(
    value: SQLiteValue | JSONValue,
    *,
    error_message: str,
) -> JSONDict:
    decoded = safe_json_deserialize(value, None)
    if not is_json_dict(decoded):
        raise ValidationError(error_message)
    return decoded


def safe_json_deserialize_required_list(
    value: SQLiteValue | JSONValue,
    *,
    error_message: str,
) -> list[JSONValue]:
    decoded = safe_json_deserialize(value, None)
    if not is_json_list(decoded):
        raise ValidationError(error_message)
    return decoded


def coerce_optional_json_from_sqlite(value: SQLiteValue) -> JSONValue | None:
    if value is None:
        return None
    decoded: JSONValue | None = value if isinstance(value, str | int | float | bool) else None
    if isinstance(decoded, str):
        try:
            decoded = parse_json_value(decoded)
        except (ValidationError, TypeError, ValueError):
            decoded = value if isinstance(value, str | int | float | bool) else None
    if not is_json_value(decoded):
        raise ValidationError(
            "Database row JSON field is not JSON-compatible.",
            details={"value_type": type(value).__name__},
        )
    return decoded


def coerce_optional_json_from_sqlite_row(row: SQLiteRow, key: str) -> JSONValue | None:
    return coerce_optional_json_from_sqlite(row.get(key))


def parse_optional_json_object_field(value: JSONValue) -> JSONDict | None:
    if value is None:
        return None
    if is_json_dict(value):
        return value
    if is_json_list(value):
        return None
    if not isinstance(value, str | int | float | bool):
        return None
    decoded = safe_json_deserialize(value, None)
    return decoded if isinstance(decoded, dict) else None


def parse_optional_json_list_field(value: JSONValue) -> list[JSONValue] | None:
    if value is None:
        return None
    if is_json_list(value):
        return value
    if is_json_dict(value):
        return None
    if not isinstance(value, str | int | float | bool):
        return None
    decoded = safe_json_deserialize(value, None)
    return decoded if isinstance(decoded, list) else None


def parse_optional_json_string_field(
    value: JSONValue | None,
    *,
    type_message: str,
    invalid_message: str,
    json_value_message: str,
) -> JSONValue | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(type_message)
    try:
        parsed = parse_json_value(value)
    except ValidationError as exception:
        raise ValidationError(invalid_message) from exception
    if not is_json_value(parsed):
        raise ValidationError(json_value_message)
    return parsed


def serialize_optional_json_list_field(value: JSONValue, *, error_message: str) -> str | None:
    if value is None:
        return None
    return serialize_required_json_list_field(value, error_message=error_message)


def serialize_required_json_list_field(value: JSONValue, *, error_message: str) -> str:
    if not is_json_list(value):
        raise ValidationError(error_message)
    try:
        return serialize_json_compact_stable_strict(value)
    except (TypeError, ValueError) as exception:
        raise ValidationError(error_message) from exception


def serialize_optional_json_object_field(value: JSONValue, *, error_message: str) -> str | None:
    if value is None:
        return None
    return serialize_required_json_object_field(value, error_message=error_message)


def serialize_required_json_object_field(value: JSONValue, *, error_message: str) -> str:
    if not is_json_dict(value):
        raise ValidationError(error_message)
    try:
        return serialize_json_compact_stable_strict(value)
    except (TypeError, ValueError) as exception:
        raise ValidationError(error_message) from exception
