"""SoAI - Default config schema: calendar [backend/core/config/default_schema/calendar.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = ("build_calendar_defaults",)


def build_calendar_defaults() -> ConfigDict:
    return {
        "CALENDAR": {
            "SYNC": {
                "ENABLED": True,
                "INTERVAL_SEC": 300,
                "WINDOW": {
                    "PAST_DAYS": 90,
                    "FUTURE_DAYS": 365,
                    "MAX_RANGE_DAYS": 365,
                },
            },
            "LIMITS": {
                "LIST_DEFAULT": 100,
                "LIST_MAX": 500,
            },
            "RECURRENCE": {
                "MAX_EXPANSIONS_PER_EVENT": 500,
            },
            "TIMEOUTS": {
                "REQUEST_SEC": 30.0,
            },
        },
    }
