"""SoAI - Centralized UTC time formatting and parsing utilities [backend/core/timing/formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import UTC, datetime

from core.errors.exceptions import ValidationError
from core.validation.integers import is_non_negative_strict_int

__all__ = (
    "datetime_to_utc_iso",
    "parse_iso_datetime_optional",
    "parse_iso_datetime_preserve_timezone",
    "parse_iso_datetime_strict",
    "timestamp_ms_to_utc_datetime",
    "timestamp_ms_to_utc_format",
    "timestamp_ms_to_utc_iso",
    "timestamp_to_utc_format",
    "timestamp_to_utc_iso",
    "timestamp_to_utc_iso_no_z",
    "timestamp_to_utc_log_format",
    "utc_now",
    "utc_now_iso",
    "utc_now_iso_compact",
    "utc_now_iso_filename_safe",
    "utc_now_log_format",
)


def datetime_to_utc_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return datetime_to_utc_iso(utc_now())


def utc_now_log_format() -> str:
    return utc_now().strftime("%Y-%m-%d %H:%M:%S")


def utc_now_iso_filename_safe() -> str:
    return utc_now().strftime("%Y-%m-%dT%H-%M-%SZ")


def utc_now_iso_compact() -> str:
    return utc_now().strftime("%Y%m%d%H%M%S")


def timestamp_to_utc_iso(epoch_seconds: float) -> str:
    return datetime_to_utc_iso(datetime.fromtimestamp(epoch_seconds, tz=UTC))


def timestamp_ms_to_utc_iso(epoch_ms: int) -> str:
    return datetime_to_utc_iso(timestamp_ms_to_utc_datetime(epoch_ms))


def timestamp_ms_to_utc_format(epoch_ms: int, format_string: str) -> str:
    return timestamp_ms_to_utc_datetime(epoch_ms).strftime(format_string)


def timestamp_ms_to_utc_datetime(epoch_ms: int) -> datetime:
    if not is_non_negative_strict_int(epoch_ms):
        raise ValidationError("Invalid epoch millisecond timestamp")
    try:
        return datetime.fromtimestamp(epoch_ms / 1000.0, tz=UTC)
    except (OSError, OverflowError, ValueError) as exception:
        raise ValidationError("Invalid epoch millisecond timestamp") from exception


def timestamp_to_utc_iso_no_z(epoch_seconds: float) -> str:
    timestamp = datetime.fromtimestamp(epoch_seconds, tz=UTC)
    return timestamp.isoformat()


def timestamp_to_utc_format(epoch_seconds: float, format_string: str) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).strftime(format_string)


def timestamp_to_utc_log_format(epoch_seconds: float) -> str:
    return timestamp_to_utc_format(epoch_seconds, "%Y-%m-%d %H:%M:%S")


def parse_iso_datetime_strict(datetime_string: str) -> datetime:
    if not datetime_string:
        raise ValidationError("Empty datetime string")
    normalized = datetime_string.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exception:
        raise ValidationError("Invalid datetime string") from exception
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_iso_datetime_preserve_timezone(datetime_string: str) -> datetime:
    if not datetime_string:
        raise ValidationError("Empty datetime string")
    normalized = datetime_string.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exception:
        raise ValidationError("Invalid datetime string") from exception


def parse_iso_datetime_optional(datetime_string: str) -> datetime | None:
    if not datetime_string:
        return None
    try:
        return parse_iso_datetime_strict(datetime_string)
    except ValidationError:
        return None
