"""SoAI - Progress percent coercion and scaling [backend/core/progress/percent.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math

from core.types.json import JSONValue

__all__ = (
    "clamp_percent",
    "coerce_optional_percent",
    "coerce_percent_or_default",
    "coerce_strict_text_percent_or_default",
    "scale_percent_range",
)


def clamp_percent(value: float) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, min(100, value))
    if not math.isfinite(value):
        return 0
    return max(0, min(100, int(value)))


def coerce_optional_percent(value: JSONValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return clamp_percent(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return clamp_percent(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            parsed = float(normalized)
        except ValueError:
            return None
        if not math.isfinite(parsed):
            return None
        return clamp_percent(parsed)
    return None


def coerce_percent_or_default(value: JSONValue, *, default: int = 0) -> int:
    parsed = coerce_optional_percent(value)
    if parsed is None:
        return clamp_percent(default)
    return parsed


def coerce_strict_text_percent_or_default(value: JSONValue, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return clamp_percent(default)
    if isinstance(value, int):
        return clamp_percent(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return clamp_percent(default)
        return clamp_percent(value)
    if isinstance(value, str):
        try:
            return clamp_percent(int(value))
        except ValueError:
            return clamp_percent(default)
    return clamp_percent(default)


def scale_percent_range(*, value: int, start_percent: int, end_percent: int) -> int:
    start = clamp_percent(start_percent)
    end = clamp_percent(end_percent)
    span = end - start
    clamped_value = clamp_percent(value)
    return start + int(span * clamped_value / 100)
