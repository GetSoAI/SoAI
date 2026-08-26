"""SoAI - SQLite numeric coercion adapters [backend/database/core/sqlite_numbers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.booleans import parse_bool_token_or_none
from core.validation.coercion import coerce_int_from_numberish
from core.validation.numbers import (
    coerce_float_from_json,
    coerce_int_from_json,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from database.core.sqlite_values import SQLiteRow, SQLiteValue

__all__ = (
    "coerce_float_from_sqlite",
    "coerce_float_value_from_sqlite",
    "coerce_int_from_sqlite",
    "coerce_non_negative_int_from_sqlite",
    "coerce_non_negative_int_from_sqlite_numberish",
    "coerce_optional_int_from_sqlite_row",
    "coerce_optional_str_from_sqlite_row",
    "coerce_required_bool_from_sqlite_row",
    "coerce_required_float_from_sqlite_row",
    "coerce_required_int_from_sqlite_row",
    "coerce_required_nonempty_str_from_sqlite_row",
)


def _coerce_sqlite_int_value(
    value: SQLiteValue,
    *,
    key: str,
    allow_null: bool,
) -> int | None:
    if value is None and allow_null:
        return None
    if isinstance(value, bool):
        raise ValidationError(
            f"Database row field '{key}' must be an int, not bool.",
            details={"key": key},
        )
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exception:
            null_suffix = " or null" if allow_null else ""
            raise ValidationError(
                f"Database row field '{key}' must be an int-compatible string{null_suffix}.",
                details={"key": key, "value": value},
                cause=exception,
            ) from exception
    if allow_null:
        raise ValidationError(
            f"Database row field '{key}' must be an int or null.",
            details={"key": key},
        )
    raise ValidationError(f"Database row missing required int field '{key}'.", details={"key": key})


def coerce_required_nonempty_str_from_sqlite_row(
    row: SQLiteRow,
    key: str,
) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(
            f"Database row missing required string field '{key}'.",
            details={"key": key},
        )
    return value


def coerce_optional_str_from_sqlite_row(
    row: SQLiteRow,
    key: str,
) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            f"Database row field '{key}' must be a string or null.",
            details={"key": key},
        )
    return value


def coerce_required_int_from_sqlite_row(row: SQLiteRow, key: str) -> int:
    parsed = _coerce_sqlite_int_value(row.get(key), key=key, allow_null=False)
    if parsed is None:
        raise ValidationError(
            f"Database row missing required int field '{key}'.",
            details={"key": key},
        )
    return parsed


def coerce_optional_int_from_sqlite_row(row: SQLiteRow, key: str) -> int | None:
    return _coerce_sqlite_int_value(row.get(key), key=key, allow_null=True)


def coerce_required_float_from_sqlite_row(row: SQLiteRow, key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool):
        raise ValidationError(
            f"Database row field '{key}' must be a float, not bool.",
            details={"key": key},
        )
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exception:
            raise ValidationError(
                f"Database row field '{key}' must be a float-compatible string.",
                details={"key": key, "value": value},
                cause=exception,
            ) from exception
    raise ValidationError(
        f"Database row missing required float field '{key}'.",
        details={"key": key},
    )


def coerce_required_bool_from_sqlite_row(row: SQLiteRow, key: str) -> bool:
    value = row.get(key)
    parsed = parse_bool_token_or_none(value)
    if parsed is not None:
        return parsed
    if isinstance(value, int):
        raise ValidationError(
            f"Database row field '{key}' int must be 0/1 for boolean.",
            details={"key": key, "value": value},
        )
    if isinstance(value, str):
        raise ValidationError(
            f"Database row field '{key}' string must be a boolean token.",
            details={"key": key, "value": value},
        )
    raise ValidationError(
        f"Database row missing required boolean field '{key}'.",
        details={"key": key},
    )


def coerce_float_from_sqlite(
    value: SQLiteValue,
    *,
    default: float | None = None,
    allow_bool: bool = False,
    allow_nonfinite: bool = False,
) -> float | None:
    return coerce_float_from_json(
        value,
        default=default,
        allow_bool=allow_bool,
        allow_nonfinite=allow_nonfinite,
    )


def coerce_float_value_from_sqlite(
    value: SQLiteValue,
    *,
    default: float = 0.0,
    allow_bool: bool = False,
    allow_nonfinite: bool = False,
) -> float:
    coerced = coerce_float_from_sqlite(
        value,
        default=default,
        allow_bool=allow_bool,
        allow_nonfinite=allow_nonfinite,
    )
    if coerced is None:
        return default
    return coerced


def coerce_int_from_sqlite(
    value: SQLiteValue,
    *,
    default: int | None = None,
    allow_bool: bool = False,
) -> int | None:
    return coerce_int_from_json(
        value,
        default=default,
        allow_bool=allow_bool,
    )


def coerce_non_negative_int_from_sqlite(
    value: SQLiteValue | JSONValue,
    *,
    default: int = 0,
    allow_bool: bool = False,
) -> int:
    if isinstance(value, bytes):
        return max(0, int(default))
    candidate = coerce_int_from_json(value, default=default, allow_bool=allow_bool)
    if candidate is None:
        return max(0, int(default))
    return max(0, candidate)


def coerce_non_negative_int_from_sqlite_numberish(
    value: SQLiteValue | JSONValue,
    *,
    default: int = 0,
) -> int:
    if isinstance(value, bytes):
        return max(0, int(default))
    candidate = coerce_int_from_numberish(value)
    if candidate is None:
        return max(0, int(default))
    return max(0, candidate)
