"""SoAI - Mail invite extraction helpers [backend/features/mail/message_invites.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import date, datetime

from icalendar import Calendar

from core.timing.datetime_conversion import temporal_value_to_epoch_ms
from core.types.json import JSONDict, JSONValue
from features.mail.internal_protocols import MailCalendarDateTimePropertyProtocol

__all__ = ("parse_calendar_invite",)


def parse_calendar_invite(payload_bytes: bytes) -> JSONDict | None:
    if not payload_bytes:
        return None
    calendar = Calendar.from_ical(payload_bytes.decode("utf-8", errors="replace"))
    method_value = calendar.get("METHOD")
    method = str(method_value).strip() if method_value is not None else None
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue
        summary_value = component.get("SUMMARY")
        summary = str(summary_value).strip() if summary_value is not None else ""
        return {
            "method": method,
            "uid": _normalize_text(component.get("UID")),
            "summary": summary or None,
            "start_at_ms": _component_dt_to_epoch_ms(component.get("DTSTART")),
            "end_at_ms": _component_dt_to_epoch_ms(component.get("DTEND")),
            "organizer": _parse_calendar_address(component.get("ORGANIZER")),
            "attendees": _parse_calendar_attendees(component.get("ATTENDEE")),
        }
    return None


def _component_dt_to_epoch_ms(value: JSONValue) -> int | None:
    dt_value = _read_calendar_property_dt(value)
    if isinstance(dt_value, datetime | date):
        return temporal_value_to_epoch_ms(dt_value)
    return None


def _parse_calendar_address(value: JSONValue) -> JSONDict | None:
    text = _normalize_text(value)
    if text is None:
        return None
    if text.lower().startswith("mailto:"):
        return {"email": text[7:], "name": None}
    return {"email": text, "name": None}


def _parse_calendar_attendees(value: JSONValue) -> list[JSONDict]:
    if isinstance(value, list):
        items = value
    elif value is None:
        items = []
    else:
        items = [value]
    attendees: list[JSONDict] = []
    for item in items:
        parsed = _parse_calendar_address(item)
        if parsed is not None:
            attendees.append(parsed)
    return attendees


def _normalize_text(value: JSONValue) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def _read_calendar_property_dt(value: JSONValue) -> date | datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime | date):
        return value
    if not isinstance(value, MailCalendarDateTimePropertyProtocol):
        return None
    dt_value = value.dt
    if isinstance(dt_value, date | datetime):
        return dt_value
    return None
