"""SoAI - Lenient numeric coercion helpers [backend/core/config/numeric_lenient.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import os
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue

    type NumericCoercible = ConfigValue

__all__ = (
    "coerce_lenient_bounded_float",
    "coerce_lenient_clamped_int",
    "coerce_lenient_positive_int",
    "coerce_positive_timeout_seconds",
    "coerce_timeout_milliseconds_or_none",
    "coerce_timeout_seconds",
)


def coerce_timeout_seconds(
    value: NumericCoercible | None,
    *,
    default: float,
) -> float:
    if value is None or isinstance(value, bool):
        return _sanitize_timeout_value(default, 0.0)
    if isinstance(value, int | float):
        try:
            return _sanitize_timeout_value(float(value), default)
        except OverflowError:
            return _sanitize_timeout_value(default, 0.0)
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return _sanitize_timeout_value(default, 0.0)
        try:
            return _sanitize_timeout_value(float(trimmed), default)
        except (OverflowError, ValueError):
            return _sanitize_timeout_value(default, 0.0)
    return _sanitize_timeout_value(default, 0.0)


def coerce_positive_timeout_seconds(
    value: NumericCoercible | None,
    *,
    default: float,
) -> float:
    timeout_seconds = coerce_timeout_seconds(value, default=default)
    if timeout_seconds > 0.0:
        return timeout_seconds
    fallback = coerce_timeout_seconds(default, default=1.0)
    return fallback if fallback > 0.0 else 1.0


def coerce_lenient_bounded_float(
    value: NumericCoercible | None,
    *,
    default: float,
    minimum: float,
    maximum: float | None = None,
) -> float:
    effective_minimum = float(minimum)
    effective_maximum = float(maximum) if maximum is not None else None
    if effective_maximum is not None and effective_maximum < effective_minimum:
        effective_maximum = effective_minimum
    if value is None or isinstance(value, bool):
        candidate = _float_or_zero(default)
    elif isinstance(value, int | float):
        candidate = _float_or_default(value, default)
    elif isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            candidate = _float_or_zero(default)
        else:
            try:
                candidate = float(trimmed)
            except (OverflowError, ValueError):
                candidate = _float_or_zero(default)
    elif isinstance(value, os.PathLike):
        candidate = coerce_lenient_bounded_float(
            os.fspath(value),
            default=default,
            minimum=minimum,
            maximum=maximum,
        )
    else:
        candidate = _float_or_zero(default)
    if not math.isfinite(candidate):
        candidate = _float_or_zero(default)
    if not math.isfinite(candidate):
        candidate = 0.0
    candidate = max(candidate, effective_minimum)
    if effective_maximum is not None and candidate > effective_maximum:
        candidate = effective_maximum
    return candidate


def coerce_lenient_positive_int(
    value: NumericCoercible | None,
    *,
    default: int,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    candidate = _coerce_lenient_int_or_default(value, default)
    if candidate < minimum:
        candidate = int(default)
    if maximum is not None and candidate > maximum:
        return maximum
    return candidate


def coerce_lenient_clamped_int(
    value: NumericCoercible | None,
    *,
    default: int,
    minimum: int,
    maximum: int | None = None,
) -> int:
    effective_minimum = int(minimum)
    effective_maximum = int(maximum) if maximum is not None else None
    if effective_maximum is not None and effective_maximum < effective_minimum:
        effective_maximum = effective_minimum
    candidate = _coerce_lenient_int_or_default(value, default)
    candidate = max(effective_minimum, candidate)
    if effective_maximum is not None:
        candidate = min(effective_maximum, candidate)
    return candidate


def coerce_timeout_milliseconds_or_none(
    value: NumericCoercible | None,
    *,
    default: int | None,
) -> int | None:
    if value is None or isinstance(value, bool):
        return default
    candidate = _coerce_timeout_milliseconds_candidate(
        value,
        default if default is not None else 0,
    )
    if candidate == 0:
        return None
    if candidate < 0:
        return default
    return candidate


def _coerce_timeout_milliseconds_candidate(
    value: NumericCoercible | None,
    default: int,
) -> int:
    if value is None or isinstance(value, bool):
        return int(default)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return int(default)
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return int(default)
    return int(default)


def _coerce_lenient_int_or_default(value: NumericCoercible | None, default: int) -> int:
    if value is None or isinstance(value, bool):
        return int(default)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return int(default)
        return int(value)
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return int(default)
        try:
            parsed = Decimal(trimmed)
            if not parsed.is_finite():
                return int(default)
            return int(parsed)
        except (InvalidOperation, OverflowError, ValueError):
            return int(default)
    return int(default)


def _sanitize_timeout_value(candidate: float, fallback: float) -> float:
    sanitized_candidate = _non_negative_finite_float_or_none(candidate)
    if sanitized_candidate is not None:
        return sanitized_candidate
    sanitized_fallback = _non_negative_finite_float_or_none(fallback)
    if sanitized_fallback is not None:
        return sanitized_fallback
    return 0.0


def _non_negative_finite_float_or_none(value: float) -> float | None:
    try:
        parsed = float(value)
    except OverflowError:
        return None
    if math.isfinite(parsed) and parsed >= 0.0:
        return parsed
    return None


def _float_or_default(value: float, default: float) -> float:
    try:
        parsed = float(value)
    except OverflowError:
        parsed = _float_or_zero(default)
    return parsed


def _float_or_zero(value: float) -> float:
    try:
        return float(value)
    except OverflowError:
        return 0.0
