"""SoAI - Strict numeric validation helpers [backend/core/validation/strict_numbers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.integers import is_non_negative_strict_int, is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_non_negative_float_strict_or_zero",
    "coerce_non_negative_int_strict_or_zero",
    "coerce_optional_non_negative_int_strict",
    "coerce_optional_positive_int_strict",
    "require_int_in_range_strict",
    "require_non_negative_int_strict",
    "require_optional_non_negative_int_strict",
    "require_positive_int_strict",
    "require_unit_interval_ratio_strict",
)


def coerce_optional_non_negative_int_strict(value: JSONValue | None) -> int | None:
    if not is_non_negative_strict_int(value):
        return None
    return value


def coerce_optional_positive_int_strict(value: JSONValue | None) -> int | None:
    if not is_strict_int(value) or value <= 0:
        return None
    return value


def coerce_non_negative_int_strict_or_zero(value: JSONValue | None) -> int:
    normalized = coerce_optional_non_negative_int_strict(value)
    if normalized is None:
        return 0
    return normalized


def coerce_non_negative_float_strict_or_zero(value: JSONValue | None) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    resolved = float(value)
    if not math.isfinite(resolved) or resolved < 0.0:
        return 0.0
    return resolved


def require_non_negative_int_strict(value: JSONValue, *, error_message: str) -> int:
    if not is_non_negative_strict_int(value):
        raise ValidationError(error_message)
    return value


def require_optional_non_negative_int_strict(value: JSONValue, *, error_message: str) -> int | None:
    if value is None:
        return None
    return require_non_negative_int_strict(value, error_message=error_message)


def require_positive_int_strict(value: JSONValue, *, error_message: str) -> int:
    if not is_strict_int(value) or value <= 0:
        raise ValidationError(error_message)
    return value


def require_unit_interval_ratio_strict(value: JSONValue, *, error_message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(error_message)
    ratio = float(value)
    if not math.isfinite(ratio) or ratio <= 0.0 or ratio >= 1.0:
        raise ValidationError(error_message)
    return ratio


def require_int_in_range_strict(
    value: JSONValue,
    *,
    minimum: int,
    maximum: int,
    error_message: str,
) -> int:
    if not is_strict_int(value):
        raise ValidationError(error_message)
    if value < minimum or value > maximum:
        raise ValidationError(error_message)
    return value
