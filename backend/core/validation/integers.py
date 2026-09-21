"""SoAI - Integer validation and coercion helpers [backend/core/validation/integers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING, TypeGuard

from core.validation.strict_integer import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_exact_int_or_none",
    "coerce_non_negative_exact_int_or_none",
    "coerce_non_negative_exact_int_or_zero",
    "coerce_non_negative_int_or_zero",
    "coerce_positive_exact_int_or_none",
    "is_non_negative_strict_int",
    "is_positive_strict_int",
    "is_strict_int",
)


def is_non_negative_strict_int[ValueT](
    value: ValueT,
    _value_type: type[ValueT] | None = None,
) -> TypeGuard[int]:
    _ = _value_type
    return is_strict_int(value) and value >= 0


def is_positive_strict_int[ValueT](
    value: ValueT,
    _value_type: type[ValueT] | None = None,
) -> TypeGuard[int]:
    _ = _value_type
    return is_strict_int(value) and value > 0


def coerce_non_negative_int_or_zero(value: int | None) -> int:
    if value is None:
        return 0
    if value < 0:
        return 0
    return int(value)


def coerce_exact_int_or_none(
    value: JSONValue,
    *,
    allow_signed_text: bool = True,
) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if not allow_signed_text and not normalized.isdigit():
            return None
        try:
            return int(normalized)
        except ValueError:
            return None
    return None


def coerce_non_negative_exact_int_or_zero(value: JSONValue) -> int:
    normalized = coerce_non_negative_exact_int_or_none(value)
    if normalized is None:
        return 0
    return normalized


def coerce_non_negative_exact_int_or_none(value: JSONValue) -> int | None:
    normalized = coerce_exact_int_or_none(value)
    if normalized is None or normalized < 0:
        return None
    return normalized


def coerce_positive_exact_int_or_none(
    value: JSONValue,
    *,
    allow_signed_text: bool = True,
) -> int | None:
    normalized = coerce_exact_int_or_none(value, allow_signed_text=allow_signed_text)
    if normalized is None or normalized <= 0:
        return None
    return normalized
