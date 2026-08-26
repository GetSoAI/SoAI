"""SoAI - Duration unit conversion primitives [backend/core/timing/durations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "MILLISECONDS_PER_DAY",
    "MILLISECONDS_PER_HOUR",
    "MILLISECONDS_PER_MINUTE",
    "days_to_ms",
    "days_to_seconds",
    "hours_to_ms",
    "hours_to_seconds",
    "minutes_to_ms",
    "minutes_to_seconds",
    "ms_to_seconds_ceil",
    "ms_to_seconds_floor",
    "seconds_to_ms",
)

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3_600
_SECONDS_PER_DAY = 86_400
_MILLISECONDS_PER_SECOND = 1_000
MILLISECONDS_PER_MINUTE = 60_000
MILLISECONDS_PER_HOUR = 3_600_000
MILLISECONDS_PER_DAY = 86_400_000


def seconds_to_ms(seconds: int | float) -> int:
    return int(seconds * _MILLISECONDS_PER_SECOND)


def minutes_to_ms(minutes: int | float) -> int:
    return int(minutes * MILLISECONDS_PER_MINUTE)


def hours_to_ms(hours: int | float) -> int:
    return int(hours * MILLISECONDS_PER_HOUR)


def days_to_ms(days: int | float) -> int:
    return int(days * MILLISECONDS_PER_DAY)


def minutes_to_seconds(minutes: int | float) -> int:
    return int(minutes * _SECONDS_PER_MINUTE)


def hours_to_seconds(hours: int | float) -> int:
    return int(hours * _SECONDS_PER_HOUR)


def days_to_seconds(days: int | float) -> int:
    return int(days * _SECONDS_PER_DAY)


def ms_to_seconds_ceil(milliseconds: int) -> int:
    return (int(milliseconds) + 999) // _MILLISECONDS_PER_SECOND


def ms_to_seconds_floor(milliseconds: int) -> int:
    return int(milliseconds) // _MILLISECONDS_PER_SECOND
