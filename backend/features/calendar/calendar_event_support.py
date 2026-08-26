"""SoAI - Calendar event mutation support [backend/features/calendar/calendar_event_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_json_object
from core.validation.strings import (
    coerce_optional_trimmed_str,
    coerce_trimmed_str_or_empty,
)
from features.calendar.calendar_record_context import require_event_calendar_id

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol

__all__ = (
    "is_remote_calendar_href",
    "load_existing_event",
    "merge_event_payload",
    "require_action",
    "require_event_payload",
    "require_id",
    "resolve_existing_remote_event_href",
    "update_invite_attendees",
)


async def load_existing_event(
    *,
    database_calendar: DatabaseCalendarProtocol,
    user_id: int,
    calendar_id: str,
    action: str,
    payload: JSONDict,
) -> JSONDict | None:
    if action != "update":
        return None
    event_id = require_id(payload.get("event_id"), "event_id is required for update.")
    event_row = await database_calendar.get_event(user_id=user_id, event_id=event_id)
    if event_row is None:
        raise ValidationError("Calendar event not found.")
    if require_event_calendar_id(event_row) != calendar_id:
        raise ValidationError("calendar_id does not match the event calendar.")
    return event_row


def merge_event_payload(
    existing_event: JSONDict | None,
    event_patch: JSONDict,
) -> JSONDict:
    return {
        "uid": _resolve_field(existing_event, event_patch, "uid"),
        "summary": _resolve_field(existing_event, event_patch, "summary", default_value=""),
        "description": _resolve_field(existing_event, event_patch, "description"),
        "location": _resolve_field(existing_event, event_patch, "location"),
        "start_at_ms": _resolve_field(existing_event, event_patch, "start_at_ms"),
        "end_at_ms": _resolve_field(existing_event, event_patch, "end_at_ms"),
        "timezone": _resolve_field(existing_event, event_patch, "timezone"),
        "all_day": _resolve_field(existing_event, event_patch, "all_day", default_value=False),
        "organizer": _resolve_field(existing_event, event_patch, "organizer"),
        "attendees": _resolve_list_field(existing_event, event_patch, "attendees"),
        "recurrence": _resolve_field(existing_event, event_patch, "recurrence"),
        "alarms": _resolve_list_field(existing_event, event_patch, "alarms"),
    }


def update_invite_attendees(
    event_row: JSONDict,
    attendee_email: str,
    response_action: str,
) -> list[JSONDict]:
    attendees_value = event_row.get("attendees")
    attendees = _copy_attendees(attendees_value)
    if not attendees:
        raise ValidationError("Calendar invite attendees are not available.")
    normalized_attendee_email = attendee_email.strip().lower()
    matched = False
    for attendee in attendees:
        address_value = attendee.get("address")
        if not isinstance(address_value, dict):
            continue
        email_value = address_value.get("email")
        email = email_value.strip().lower() if isinstance(email_value, str) else ""
        if email and email == normalized_attendee_email:
            attendee["status"] = response_action
            matched = True
            break
    if not matched:
        raise ValidationError(
            "Calendar invite attendee could not be matched to the current account.",
        )
    return attendees


def resolve_existing_remote_event_href(existing_event: JSONDict | None) -> str | None:
    if existing_event is None:
        return None
    remote_href = coerce_optional_trimmed_str(existing_event.get("remote_href"))
    if remote_href is None or not is_remote_calendar_href(remote_href):
        return None
    return remote_href


def require_action(value: JSONValue, allowed: set[str]) -> str:
    normalized = require_id(value, "action is invalid.")
    if normalized not in allowed:
        raise ValidationError(
            (
                "calendar_event_update.action is invalid."
                if allowed == {"create", "update", "delete"}
                else "calendar_invite_respond.action is invalid."
            ),
        )
    return normalized


def require_event_payload(value: JSONValue) -> JSONDict:
    return require_json_object(
        value,
        label="event",
        build_error=ValidationError,
        invalid_message="event is required.",
    )


def require_id(value: JSONValue, message: str) -> str:
    normalized = coerce_trimmed_str_or_empty(value)
    if not normalized:
        raise ValidationError(message)
    return normalized


def is_remote_calendar_href(remote_href: str) -> bool:
    parsed = urlsplit(remote_href)
    return parsed.scheme in {"http", "https"}


def _resolve_field(
    existing_event: JSONDict | None,
    event_patch: JSONDict,
    key: str,
    default_value: JSONValue = None,
) -> JSONValue:
    if key in event_patch:
        return event_patch.get(key)
    if existing_event is not None:
        return existing_event.get(key)
    return default_value


def _resolve_list_field(
    existing_event: JSONDict | None,
    event_patch: JSONDict,
    key: str,
) -> list[JSONDict]:
    patched_value = event_patch.get(key)
    if isinstance(patched_value, list):
        return [dict(item) for item in patched_value if isinstance(item, dict)]
    existing_value = existing_event.get(key) if existing_event is not None else None
    if isinstance(existing_value, list):
        return [dict(item) for item in existing_value if isinstance(item, dict)]
    return []


def _copy_attendees(attendees_value: JSONValue) -> list[JSONDict]:
    if not isinstance(attendees_value, list):
        return []
    attendees: list[JSONDict] = []
    for item in attendees_value:
        if not isinstance(item, dict):
            continue
        copied_attendee: JSONDict = {}
        for key, value in item.items():
            if isinstance(key, str):
                copied_attendee[key] = value
        attendees.append(copied_attendee)
    return attendees
