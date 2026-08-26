"""SoAI - UTC datetime conversion primitives [backend/core/timing/datetime_conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import UTC, date, datetime, time

__all__ = (
    "coerce_datetime_to_utc",
    "datetime_to_epoch_ms",
    "temporal_value_to_epoch_ms",
)


def coerce_datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def datetime_to_epoch_ms(value: datetime) -> int:
    return int(coerce_datetime_to_utc(value).timestamp() * 1000)


def temporal_value_to_epoch_ms(value: date | datetime) -> int:
    if isinstance(value, datetime):
        return datetime_to_epoch_ms(value)
    return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp() * 1000)
