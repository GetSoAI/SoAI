"""SoAI - Retry backoff and Retry-After parsing [backend/core/timing/retry_backoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import secrets
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms, epoch_seconds
from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "compute_exponential_backoff_milliseconds",
    "compute_exponential_backoff_seconds",
    "compute_uniform_delay_seconds",
    "parse_retry_after_seconds",
    "parse_retry_after_milliseconds",
)


def compute_exponential_backoff_seconds(
    attempt: int,
    *,
    base_seconds: float,
    maximum_seconds: float,
    jitter_seconds: float = 0.0,
    jitter_ratio: float = 0.0,
) -> float:
    normalized_attempt = max(0, int(attempt))
    maximum = float(maximum_seconds)
    base = float(base_seconds)
    if not math.isfinite(maximum) or not math.isfinite(base) or maximum <= 0.0 or base <= 0.0:
        return 0.0
    try:
        delay = base * (2.0**normalized_attempt)
    except OverflowError:
        delay = maximum
    capped = min(maximum, max(0.0, delay))
    jitter_limit = max(float(jitter_seconds), capped * float(jitter_ratio))
    if not math.isfinite(jitter_limit) or jitter_limit <= 0.0:
        return capped
    jitter = secrets.SystemRandom().uniform(0.0, jitter_limit)
    return min(maximum, capped + jitter)


def compute_exponential_backoff_milliseconds(
    attempt: int,
    *,
    base_milliseconds: int,
    maximum_milliseconds: int,
    jitter_milliseconds: int = 0,
) -> int:
    delay_seconds = compute_exponential_backoff_seconds(
        attempt,
        base_seconds=float(max(0, int(base_milliseconds))) / 1000.0,
        maximum_seconds=float(max(0, int(maximum_milliseconds))) / 1000.0,
        jitter_seconds=float(max(0, int(jitter_milliseconds))) / 1000.0,
    )
    return int(delay_seconds * 1000.0)


def compute_uniform_delay_seconds(*, minimum_seconds: float, maximum_seconds: float) -> float:
    minimum = float(minimum_seconds)
    maximum = float(maximum_seconds)
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        return 0.0
    ordered_minimum = min(minimum, maximum)
    ordered_maximum = max(minimum, maximum)
    lower = max(0.0, ordered_minimum)
    upper = max(0.0, ordered_maximum)
    if upper <= lower:
        return lower
    return secrets.SystemRandom().uniform(lower, upper)


def parse_retry_after_seconds(value: str | None, *, default_seconds: int = 0) -> int:
    default = max(0, int(default_seconds))
    if value is None:
        return default
    normalized = value.strip()
    if not normalized:
        return default
    numeric_seconds: int | None
    try:
        numeric_seconds = max(0, int(float(normalized)))
    except (OverflowError, ValueError):
        numeric_seconds = None
    if numeric_seconds is not None:
        return numeric_seconds
    try:
        parsed = parsedate_to_datetime(normalized)
    except (TypeError, ValueError, IndexError, OverflowError):
        return default
    return max(0, int(parsed.timestamp()) - epoch_seconds())


def parse_retry_after_milliseconds(
    value: JSONValue,
    *,
    default_milliseconds: int,
    maximum_milliseconds: int,
) -> int:
    maximum = max(0, maximum_milliseconds)
    default = min(max(0, default_milliseconds), maximum)
    seconds = coerce_float_from_json(value, default=None)
    if seconds is not None:
        return min(maximum, max(0, math.ceil(seconds * 1000.0)))
    if not isinstance(value, str):
        return default
    try:
        parsed = parsedate_to_datetime(value.strip())
    except (TypeError, ValueError, IndexError, OverflowError):
        return default
    delay = math.ceil((parsed.timestamp() * 1000.0) - epoch_ms())
    return min(maximum, max(0, delay))
