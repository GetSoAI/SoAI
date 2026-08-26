"""SoAI - Automation local time helpers [backend/core/automation/automation_local_time.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.errors.exceptions import ValidationError
from core.timing.timezones import normalize_timezone_name, resolve_zoneinfo_optional

__all__ = (
    "last_day_of_month",
    "local_naive_from_utc_ms",
    "parse_start_local",
    "require_timezone",
    "resolve_local_naive_to_utc_ms",
)

_START_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


def require_timezone(timezone_name: str) -> ZoneInfo:
    normalized = normalize_timezone_name(timezone_name)
    if not normalized:
        raise ValidationError("Automation timezone is required.")
    try:
        resolved = resolve_zoneinfo_optional(normalized)
    except ZoneInfoNotFoundError as exception:
        raise ValidationError(f"Unsupported automation timezone '{normalized}'.") from exception
    if resolved is None:
        raise ValidationError("Automation timezone is required.")
    return resolved


def parse_start_local(start_local: str) -> datetime:
    normalized = str(start_local or "").strip()
    if not normalized:
        raise ValidationError("Automation start_local is required.")
    try:
        parsed = datetime.strptime(normalized, _START_LOCAL_FORMAT)
    except ValueError as exception:
        raise ValidationError("Automation start_local must match YYYY-MM-DDTHH:mm.") from exception
    if parsed.strftime(_START_LOCAL_FORMAT) != normalized:
        raise ValidationError("Automation start_local must match YYYY-MM-DDTHH:mm.")
    return parsed


def local_naive_from_utc_ms(utc_ms: int, timezone_name: str) -> datetime:
    timezone = require_timezone(timezone_name)
    aware_utc = datetime.fromtimestamp(utc_ms / 1000.0, tz=UTC)
    return aware_utc.astimezone(timezone).replace(tzinfo=None)


def resolve_local_naive_to_utc_ms(local_naive: datetime, timezone_name: str) -> int:
    timezone = require_timezone(timezone_name)
    aware_fold_zero = local_naive.replace(tzinfo=timezone, fold=0)
    aware_fold_one = local_naive.replace(tzinfo=timezone, fold=1)
    if aware_fold_zero.utcoffset() != aware_fold_one.utcoffset():
        return int(aware_fold_zero.astimezone(UTC).timestamp() * 1000.0)
    roundtrip = aware_fold_zero.astimezone(UTC).astimezone(timezone)
    if roundtrip.replace(tzinfo=None) != local_naive:
        return int(roundtrip.astimezone(UTC).timestamp() * 1000.0)
    return int(aware_fold_zero.astimezone(UTC).timestamp() * 1000.0)


def last_day_of_month(year: int, month: int) -> int:
    next_month = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return (next_month - datetime.resolution).day
