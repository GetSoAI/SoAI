"""SoAI - Timezone resolution helpers [backend/core/timing/timezones.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.errors.exceptions import ValidationError

__all__ = (
    "normalize_timezone_name",
    "resolve_zoneinfo_optional",
    "resolve_zoneinfo_required",
)


def normalize_timezone_name(timezone_name: str | None) -> str:
    return str(timezone_name or "").strip()


def resolve_zoneinfo_optional(timezone_name: str | None) -> ZoneInfo | None:
    normalized = normalize_timezone_name(timezone_name)
    if not normalized:
        return None
    return ZoneInfo(normalized)


def resolve_zoneinfo_required(timezone_name: str, *, label: str = "timezone") -> ZoneInfo:
    normalized = normalize_timezone_name(timezone_name)
    if not normalized:
        raise ValidationError(f"{label} is required.")
    try:
        return ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exception:
        raise ValidationError(f"Unknown timezone: {normalized}") from exception
