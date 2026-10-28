"""SoAI - Retry backoff and Retry-After parsing [backend/core/timing/retry_backoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import secrets
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from core.validation.numbers import coerce_float_from_json

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "compute_exponential_backoff_milliseconds",
    "compute_exponential_backoff_seconds",
    "compute_uniform_delay_seconds",
    "parse_retry_after_seconds",
    "parse_retry_after_milliseconds",
    "normalize_retry_after_header",
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


def _retry_after_delay_seconds(value: JSONValue) -> float | None:
    if isinstance(value, str) and (len(value) > 128 or "\r" in value or "\n" in value):
        return None
    numeric_seconds = coerce_float_from_json(value, default=None)
    if numeric_seconds is not None:
        return numeric_seconds if abs(numeric_seconds) <= JAVASCRIPT_SAFE_INTEGER_MAX else None
    if not isinstance(value, str):
        return None
    try:
        parsed = parsedate_to_datetime(value.strip())
        if parsed.tzinfo is None:
            return None
        delay_seconds = parsed.timestamp() - epoch_ms() / 1000.0
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return max(0.0, delay_seconds)


def parse_retry_after_seconds(
    value: str | None,
    *,
    default_seconds: int = 0,
    round_up: bool = False,
) -> int:
    seconds = _retry_after_delay_seconds(value)
    if seconds is None:
        return max(0, int(default_seconds))
    return max(0, math.ceil(seconds) if round_up else int(seconds))


def normalize_retry_after_header(value: str | None, *, milliseconds: bool = False) -> str | None:
    if milliseconds:
        if not isinstance(value, str) or len(value) > 128 or "\r" in value or "\n" in value:
            return None
        seconds = coerce_float_from_json(value, default=None)
        seconds = seconds / 1000.0 if seconds is not None else None
    else:
        seconds = _retry_after_delay_seconds(value)
    if seconds is None or seconds < 0 or seconds > JAVASCRIPT_SAFE_INTEGER_MAX:
        return None
    return str(math.ceil(seconds))


def parse_retry_after_milliseconds(
    value: JSONValue,
    *,
    default_milliseconds: int,
    maximum_milliseconds: int,
) -> int:
    maximum = max(0, maximum_milliseconds)
    default = min(max(0, default_milliseconds), maximum)
    seconds = _retry_after_delay_seconds(value)
    if seconds is not None:
        return min(maximum, max(0, math.ceil(seconds * 1000.0)))
    return default
