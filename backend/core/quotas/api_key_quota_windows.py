"""SoAI - API key quota window definitions and helpers [backend/core/quotas/api_key_quota_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.durations import hours_to_ms, seconds_to_ms
from core.validation.integers import coerce_exact_int_or_none
from core.validation.requirements import require_positive_exact_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ACTIVE_API_KEY_QUOTA_MODES",
    "API_KEY_QUOTA_MODES",
    "coerce_api_key_quota_positive_limit",
    "compute_reset_at_ms",
    "normalize_api_key_quota_expected_mode",
    "normalize_api_key_quota_mode",
    "normalize_api_key_quota_row_mode",
    "normalize_hourly_window_hours",
    "parse_api_key_quota_hourly_window_hours",
    "require_positive_optional_quota_int",
    "resolve_window_ms",
)

DAILY_WINDOW_SECONDS = 86_400
WEEKLY_WINDOW_SECONDS = 604_800
MONTHLY_WINDOW_SECONDS = 2_592_000

WINDOW_NAMES: tuple[str, ...] = ("hourly", "daily", "weekly", "monthly")
API_KEY_QUOTA_MODES: frozenset[str] = frozenset(("none", "tokens", "requests"))
ACTIVE_API_KEY_QUOTA_MODES: frozenset[str] = frozenset(("tokens", "requests"))


def require_positive_optional_quota_int(
    value: int | None,
    *,
    error_message: str,
) -> int | None:
    if value is None:
        return None
    if value <= 0:
        raise ValidationError(error_message)
    return value


def normalize_api_key_quota_mode(value: str, *, empty_message: str) -> str:
    text = value.strip()
    if not text:
        raise ValidationError(empty_message)
    normalized = text.lower()
    if normalized not in API_KEY_QUOTA_MODES:
        raise ValidationError("mode must be one of: none, tokens, requests.")
    return normalized


def normalize_api_key_quota_row_mode(value: JSONValue | bytes | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8")
        except UnicodeDecodeError:
            return "none"
    else:
        text = str(value)
    mode = text.strip().lower()
    return mode if mode in API_KEY_QUOTA_MODES else "none"


def normalize_api_key_quota_expected_mode(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in ACTIVE_API_KEY_QUOTA_MODES:
        raise ValidationError("expected_mode must be one of: tokens, requests.")
    return normalized


def coerce_api_key_quota_positive_limit(
    value: JSONDict | None,
    *,
    field_name: str,
) -> int | None:
    if value is None:
        return None
    raw_limit = value.get("limit_units")
    if raw_limit is None:
        return None
    error_message = f"{field_name}.limit_units must be a positive integer."
    return _coerce_positive_quota_integer(raw_limit, error_message=error_message, allow_blank=True)


def parse_api_key_quota_hourly_window_hours(value: JSONValue | None) -> int | None:
    if value is None:
        return None
    return _coerce_quota_integer(
        value,
        error_message="hourly.window_hours must be a positive integer.",
        allow_blank=True,
    )


def normalize_hourly_window_hours(value: int | None, *, max_hours: int) -> int | None:
    if value is None:
        return None
    hours = int(value)
    if hours <= 0:
        raise ValidationError("hourly.window_hours must be greater than zero.")
    if hours > max_hours:
        raise ValidationError(f"hourly.window_hours must be <= {max_hours}.")
    return hours


def resolve_window_ms(*, window_name: str, hourly_window_hours: int | None) -> int:
    if window_name == "hourly":
        if hourly_window_hours is None:
            raise ValidationError("hourly.window_hours is required for hourly quotas.")
        return hours_to_ms(int(hourly_window_hours))
    if window_name == "daily":
        return seconds_to_ms(DAILY_WINDOW_SECONDS)
    if window_name == "weekly":
        return seconds_to_ms(WEEKLY_WINDOW_SECONDS)
    if window_name == "monthly":
        return seconds_to_ms(MONTHLY_WINDOW_SECONDS)
    raise ValidationError(f"Invalid quota window_name: {window_name}")


def compute_reset_at_ms(*, window_start_ts_ms: int, window_ms: int) -> int:
    return int(window_start_ts_ms) + int(window_ms)


def _coerce_positive_quota_integer(
    value: JSONValue,
    *,
    error_message: str,
    allow_blank: bool,
) -> int | None:
    if isinstance(value, str) and not value.strip() and allow_blank:
        return None
    return require_positive_exact_int(
        value,
        type_message=error_message,
        range_message=error_message,
    )


def _coerce_quota_integer(
    value: JSONValue,
    *,
    error_message: str,
    allow_blank: bool,
) -> int | None:
    if isinstance(value, str) and not value.strip() and allow_blank:
        return None
    normalized = coerce_exact_int_or_none(value)
    if normalized is None:
        raise ValidationError(error_message)
    return normalized
