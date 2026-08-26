"""SoAI - Calendar ICS value helpers [backend/features/calendar/calendar_ics_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfoNotFoundError

from icalendar import vCalAddress, vText

from core.errors.exceptions import ValidationError
from core.timing.datetime_conversion import temporal_value_to_epoch_ms
from core.timing.formatting import timestamp_ms_to_utc_datetime
from core.timing.timezones import resolve_zoneinfo_optional
from core.types.json import JSONDict, JSONValue
from core.validation.booleans import parse_true_false_token_or_none
from core.validation.strict_numbers import require_positive_int_strict

__all__ = (
    "build_address_property",
    "encode_attendee_status",
    "event_value_to_epoch_ms",
    "extract_timezone_name",
    "normalize_attendee_status",
    "optional_ics_text",
    "parse_address_property",
    "parse_rsvp",
    "require_event_text",
    "require_event_timestamp",
    "resolve_event_uid",
    "timestamp_to_event_value",
)


def optional_ics_text(value: JSONValue | str | bytes | float | bool | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict | list):
        return None
    if isinstance(value, bytes):
        normalized = value.decode("utf-8", errors="replace").strip()
        return normalized or None
    normalized = str(value).strip()
    return normalized or None


def require_event_text(
    value: JSONValue | str | bytes | float | bool | None,
    label: str,
) -> str:
    normalized = optional_ics_text(value)
    if normalized is None:
        raise ValidationError(f"{label} is required.")
    return normalized


def require_event_timestamp(value: JSONValue | int | bool | None, label: str) -> int:
    return require_positive_int_strict(value, error_message=f"{label} is required.")


def resolve_event_uid(event_payload: JSONDict, uid: str | None) -> str:
    normalized_uid = optional_ics_text(uid)
    if normalized_uid is not None:
        return normalized_uid
    payload_uid = optional_ics_text(event_payload.get("uid"))
    if payload_uid is not None:
        return payload_uid
    return f"soai-{uuid.uuid4().hex}"


def timestamp_to_event_value(*, event_payload: JSONDict, timestamp_ms: int) -> date | datetime:
    all_day = event_payload.get("all_day") is True
    timestamp_dt = timestamp_ms_to_utc_datetime(timestamp_ms)
    if all_day:
        return timestamp_dt.date()
    timezone_name = optional_ics_text(event_payload.get("timezone"))
    try:
        zone = resolve_zoneinfo_optional(timezone_name)
    except ZoneInfoNotFoundError as exception:
        raise ValidationError("timezone is invalid.") from exception
    if zone is None:
        return timestamp_dt
    return timestamp_dt.astimezone(zone)


def event_value_to_epoch_ms(value: date | datetime) -> int:
    return temporal_value_to_epoch_ms(value)


def extract_timezone_name(
    timezone_id: str | bytes | float | bool | None,
) -> str | None:
    return optional_ics_text(timezone_id)


def build_address_property(address: JSONDict) -> vCalAddress | None:
    email_value = address.get("email")
    email = email_value.strip() if isinstance(email_value, str) else ""
    if not email:
        return None
    property_value = vCalAddress(f"MAILTO:{email}")
    common_name = optional_ics_text(address.get("name"))
    if common_name is not None:
        property_value.params["CN"] = vText(common_name)
    return property_value


def parse_address_property(
    *,
    raw_value: str | bytes | None,
    common_name: str | bytes | float | bool | None,
) -> JSONDict | None:
    normalized_raw = optional_ics_text(raw_value)
    if normalized_raw is None:
        return None
    email = normalized_raw[7:] if normalized_raw.lower().startswith("mailto:") else normalized_raw
    return {
        "email": email,
        "name": optional_ics_text(common_name),
    }


def parse_rsvp(value: str | bytes | float | bool | None) -> bool | None:
    normalized = optional_ics_text(value)
    if normalized is None:
        return None
    return parse_true_false_token_or_none(normalized)


def normalize_attendee_status(
    value: str | bytes | float | bool | None,
) -> str | None:
    normalized = optional_ics_text(value)
    if normalized is None:
        return None
    upper_value = normalized.upper().replace("_", "-")
    if upper_value == "ACCEPT":
        return "accepted"
    if upper_value == "ACCEPTED":
        return "accepted"
    if upper_value == "DECLINE":
        return "declined"
    if upper_value == "DECLINED":
        return "declined"
    if upper_value == "TENTATIVE":
        return "tentative"
    if upper_value == "NEEDS-ACTION":
        return "needs_action"
    return normalized.strip().lower().replace("-", "_")


def encode_attendee_status(status: str | None) -> str | None:
    normalized = optional_ics_text(status)
    if normalized is None:
        return None
    lowered = normalized.lower().replace("-", "_")
    if lowered in {"accept", "accepted"}:
        return "ACCEPTED"
    if lowered in {"decline", "declined"}:
        return "DECLINED"
    if lowered == "tentative":
        return "TENTATIVE"
    if lowered == "needs_action":
        return "NEEDS-ACTION"
    return normalized.upper()
