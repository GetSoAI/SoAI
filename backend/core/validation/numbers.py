"""SoAI - Numeric coercion helpers for JSON input [backend/core/validation/numbers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_float_from_json",
    "coerce_int_clamped_with_default",
    "coerce_int_from_json",
    "coerce_int_in_range_with_default",
    "coerce_optional_float_from_json",
)


def coerce_int_from_json(
    value: JSONValue,
    *,
    default: int | None = None,
    allow_bool: bool = False,
    parse_float_strings: bool = False,
    round_float_strings: bool = False,
) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        if allow_bool:
            return int(value)
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return default
        if round_float_strings:
            return int(round(value))
        if value.is_integer():
            return int(value)
        return default
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return default
        if parse_float_strings:
            try:
                parsed = float(trimmed)
            except ValueError:
                return default
            if not math.isfinite(parsed):
                return default
            if round_float_strings:
                return int(round(parsed))
            if parsed.is_integer():
                return int(parsed)
            return default
        try:
            return int(trimmed)
        except (TypeError, ValueError):
            return default
    return default


def coerce_float_from_json(
    value: JSONValue,
    *,
    default: float | None,
    allow_bool: bool = False,
    allow_nonfinite: bool = False,
) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return float(value) if allow_bool else default
    if isinstance(value, int | float):
        parsed = float(value)
        if (not allow_nonfinite) and not math.isfinite(parsed):
            return default
        return parsed
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return default
        try:
            parsed = float(trimmed)
        except ValueError:
            return default
        if (not allow_nonfinite) and not math.isfinite(parsed):
            return default
        return parsed
    return default


def coerce_optional_float_from_json(
    value: JSONValue,
    *,
    allow_bool: bool = False,
    allow_nonfinite: bool = False,
) -> float | None:
    return coerce_float_from_json(
        value,
        default=None,
        allow_bool=allow_bool,
        allow_nonfinite=allow_nonfinite,
    )


def coerce_int_in_range_with_default(
    value: JSONValue,
    *,
    default: int,
    fallback: int,
    minimum: int,
    maximum: int,
) -> int:
    default_value = default if minimum <= default <= maximum else fallback
    if isinstance(value, bool):
        return default_value
    candidate: int | None = None
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, float):
        if value.is_integer():
            candidate = int(value)
    elif isinstance(value, str):
        trimmed = value.strip()
        if trimmed and trimmed.lstrip("-").isdigit():
            try:
                candidate = int(trimmed)
            except (TypeError, ValueError, OverflowError):
                return default_value
    if candidate is None:
        return default_value
    if candidate < minimum or candidate > maximum:
        return default_value
    return candidate


def coerce_int_clamped_with_default(
    value: JSONValue,
    *,
    default: int,
    fallback: int,
    minimum: int,
    maximum: int,
) -> int:
    default_value = default if minimum <= default <= maximum else fallback
    candidate = coerce_int_from_json(
        value,
        default=None,
        allow_bool=False,
        parse_float_strings=True,
        round_float_strings=False,
    )
    if candidate is None:
        return default_value
    if candidate < minimum:
        return minimum
    if candidate > maximum:
        return maximum
    return candidate
