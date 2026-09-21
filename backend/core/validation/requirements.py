"""SoAI - Validation requirement utilities [backend/core/validation/requirements.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.types.json import JSONValue
from core.validation.coercion import coerce_int
from core.validation.integers import coerce_exact_int_or_none
from core.validation.numberish import require_int_from_numberish
from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = (
    "coerce_optional_int",
    "require_float",
    "require_int",
    "require_non_negative_exact_int",
    "require_non_negative_int",
    "require_nonempty_str",
    "require_optional_str",
    "require_positive_exact_int",
    "require_positive_int",
    "require_str",
)


def require_positive_exact_int(
    value: JSONValue,
    *,
    type_message: str,
    range_message: str,
) -> int:
    normalized = coerce_exact_int_or_none(value)
    if normalized is None:
        raise ValidationError(type_message)
    if normalized <= 0:
        raise ValidationError(range_message)
    return normalized


def require_non_negative_exact_int(
    value: JSONValue,
    *,
    type_message: str,
    range_message: str,
) -> int:
    normalized = coerce_exact_int_or_none(value)
    if normalized is None:
        raise ValidationError(type_message)
    if normalized < 0:
        raise ValidationError(range_message)
    return normalized


def require_int(value: JSONValue, *, field: str) -> int:
    return require_int_from_numberish(
        value,
        field=field,
        bool_message=f"{field} must be numeric.",
        invalid_message=f"{field} must be numeric.",
    )


def require_float(value: JSONValue, *, field: str) -> float:
    parsed = coerce_float_from_json(
        value,
        default=None,
        allow_bool=False,
        allow_nonfinite=False,
    )
    if parsed is None:
        raise ValidationError(f"{field} must be numeric.")
    return parsed


def require_str(value: JSONValue, *, field: str) -> str:
    if isinstance(value, str):
        return value
    raise StateError(f"{field} must be a string.")


def require_nonempty_str(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string.")
    trimmed = value.strip()
    if not trimmed:
        raise ValidationError(f"{field} must not be empty.")
    return trimmed


def require_optional_str(value: JSONValue, *, field: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise StateError(f"{field} must be a string or null.")


def require_positive_int(value: JSONValue | ConfigValue, *, name: str) -> int:
    if not isinstance(value, str | int | float | bool) and value is not None:
        raise ValidationError(f"{name} must be a positive integer")
    numeric = coerce_exact_int_or_none(value)
    if numeric is None:
        raise ValidationError(f"{name} must be a positive integer")
    if numeric <= 0:
        raise ValidationError(f"{name} must be a positive integer")
    return numeric


def require_non_negative_int(value: JSONValue | ConfigValue, *, error_message: str) -> int:
    if not isinstance(value, str | int | float | bool) and value is not None:
        raise ValidationError(error_message)
    numeric = coerce_exact_int_or_none(value)
    if numeric is None:
        raise ValidationError(error_message)
    if numeric < 0:
        raise ValidationError(error_message)
    return numeric


def coerce_optional_int(
    value: JSONValue | ConfigValue,
    *,
    _value_type: type[int] | None = None,
) -> int | None:
    if _value_type is not None and _value_type is not int:
        raise StateError("_value_type must be int or None.")
    if value is None:
        return None
    if isinstance(value, bool | int | float | str | bytes | bytearray):
        return coerce_int(value)
    return None
