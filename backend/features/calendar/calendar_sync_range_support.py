"""SoAI - Calendar sync range support [backend/features/calendar/calendar_sync_range_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.clamped_numeric import read_config_int_min_clamped
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.timing.durations import days_to_ms
from core.timing.epoch import epoch_ms
from core.timing.windows import validate_strict_window_range

__all__ = (
    "resolve_default_window",
    "validate_window_range",
)


def resolve_default_window(config: ConfigProtocol) -> tuple[int, int]:
    now_ms = epoch_ms()
    past_days = read_config_int_min_clamped(
        config,
        "INTEGRATIONS.CALENDAR.SYNC.WINDOW.PAST_DAYS",
        0,
        minimum=1,
    )
    future_days = read_config_int_min_clamped(
        config,
        "INTEGRATIONS.CALENDAR.SYNC.WINDOW.FUTURE_DAYS",
        0,
        minimum=1,
    )
    return now_ms - days_to_ms(past_days), now_ms + days_to_ms(future_days)


def validate_window_range(
    *,
    config: ConfigProtocol,
    window_start_ms: int,
    window_end_ms: int,
) -> None:
    validate_strict_window_range(
        start_ms=window_start_ms,
        end_ms=window_end_ms,
        message="window_end_ms must be greater than window_start_ms.",
    )
    max_range_days = read_config_int_min_clamped(
        config,
        "INTEGRATIONS.CALENDAR.SYNC.WINDOW.MAX_RANGE_DAYS",
        0,
        minimum=1,
    )
    max_range_ms = days_to_ms(max_range_days)
    if (window_end_ms - window_start_ms) > max_range_ms:
        raise ValidationError("Requested calendar sync window exceeds the configured max range.")
