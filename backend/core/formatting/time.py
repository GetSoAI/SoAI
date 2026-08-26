"""SoAI - Human-readable time formatting [backend/core/formatting/time.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "format_duration_hhmm",
    "format_interval_hours",
)


def format_duration_hhmm(duration_sec: float) -> str:
    try:
        duration_sec = float(duration_sec)
    except (TypeError, ValueError):
        duration_sec = 0.0
    if duration_sec <= 0:
        return "0:00"
    total_minutes = int(duration_sec // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


def format_interval_hours(interval_hours: float) -> str:
    try:
        interval_hours = float(interval_hours)
    except (TypeError, ValueError):
        interval_hours = 0.0
    if interval_hours <= 0:
        return "disabled"
    if interval_hours.is_integer():
        return f"{int(interval_hours)}h"
    return format_duration_hhmm(interval_hours * 3600)
