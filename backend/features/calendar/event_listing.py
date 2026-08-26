"""SoAI - Calendar event listing helpers [backend/features/calendar/event_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.durations import days_to_ms
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.calendar.calendar_alarm_values import (
    calendar_alarm_to_payload,
    normalize_alarm_entries,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
    "build_event_payload",
    "event_sort_key",
    "filter_events",
    "resolve_window_bounds",
)


def resolve_window_bounds(config: ConfigProtocol, arguments: JSONDict) -> tuple[int, int]:
    now_ms = epoch_ms()
    past_days = int(config.get_int("INTEGRATIONS.CALENDAR.SYNC.WINDOW.PAST_DAYS"))
    future_days = int(config.get_int("INTEGRATIONS.CALENDAR.SYNC.WINDOW.FUTURE_DAYS"))
    default_start_ms = now_ms - days_to_ms(past_days)
    default_end_ms = now_ms + days_to_ms(future_days)
    start_value = arguments.get("window_start_ms")
    end_value = arguments.get("window_end_ms")
    start_ms = start_value if isinstance(start_value, int) and start_value > 0 else default_start_ms
    end_ms = end_value if isinstance(end_value, int) and end_value > start_ms else default_end_ms
    return start_ms, end_ms


def filter_events(
    events: list[JSONDict],
    *,
    arguments: JSONDict,
    window_start_ms: int,
    window_end_ms: int,
) -> list[JSONDict]:
    filtered = [
        event
        for event in events
        if _event_overlaps_window(
            event,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        )
    ]
    query = coerce_optional_trimmed_str(arguments.get("query"))
    if query is not None:
        lowered_query = query.lower()
        filtered = [event for event in filtered if lowered_query in _event_search_blob(event)]
    attendee = coerce_optional_trimmed_str(arguments.get("attendee"))
    if attendee is not None:
        lowered_attendee = attendee.lower()
        filtered = [event for event in filtered if lowered_attendee in _attendee_blob(event)]
    organizer = coerce_optional_trimmed_str(arguments.get("organizer"))
    if organizer is not None:
        lowered_organizer = organizer.lower()
        filtered = [event for event in filtered if lowered_organizer in _organizer_blob(event)]
    return filtered


def event_sort_key(item: JSONDict, order_by: str) -> tuple[str | int, str]:
    sort_value = item.get(order_by)
    if isinstance(sort_value, int):
        return (sort_value, str(item.get("event_id") or ""))
    if isinstance(sort_value, str):
        return (sort_value.lower(), str(item.get("event_id") or ""))
    return ("", str(item.get("event_id") or ""))


def build_event_payload(
    *,
    calendar_id: str,
    existing_event: JSONDict | None,
    event_payload: JSONDict,
) -> JSONDict:
    remote_href_value = event_payload.get("remote_href")
    remote_href = (
        remote_href_value.strip()
        if isinstance(remote_href_value, str) and remote_href_value.strip()
        else None
    )
    if remote_href is None and existing_event is not None:
        existing_remote_href = existing_event.get("remote_href")
        if isinstance(existing_remote_href, str) and existing_remote_href.strip():
            remote_href = existing_remote_href.strip()
    if remote_href is None:
        event_id_value = (
            existing_event.get("id")
            if existing_event is not None
            else event_payload.get("event_id")
        )
        event_id = (
            event_id_value.strip()
            if isinstance(event_id_value, str) and event_id_value.strip()
            else f"local-{epoch_ms()}"
        )
        remote_href = f"local://calendar/{calendar_id}/{event_id}"
    attendees_value = event_payload.get("attendees")
    attendees = attendees_value if isinstance(attendees_value, list) else []
    alarms = [
        calendar_alarm_to_payload(alarm)
        for alarm in normalize_alarm_entries(event_payload.get("alarms"))
    ]
    return {
        "remote_href": remote_href,
        "etag": (
            event_payload.get("etag")
            if "etag" in event_payload
            else (existing_event.get("etag") if existing_event is not None else None)
        ),
        "uid": (
            event_payload.get("uid")
            if "uid" in event_payload
            else (existing_event.get("uid") if existing_event is not None else None)
        ),
        "summary": (
            event_payload.get("summary")
            if "summary" in event_payload
            else (existing_event.get("summary") if existing_event is not None else "")
        ),
        "description": (
            event_payload.get("description")
            if "description" in event_payload
            else (existing_event.get("description") if existing_event is not None else None)
        ),
        "location": (
            event_payload.get("location")
            if "location" in event_payload
            else (existing_event.get("location") if existing_event is not None else None)
        ),
        "start_at_ms": (
            event_payload.get("start_at_ms")
            if "start_at_ms" in event_payload
            else (existing_event.get("start_at_ms") if existing_event is not None else None)
        ),
        "end_at_ms": (
            event_payload.get("end_at_ms")
            if "end_at_ms" in event_payload
            else (existing_event.get("end_at_ms") if existing_event is not None else None)
        ),
        "updated_at_ms": epoch_ms(),
        "timezone": (
            event_payload.get("timezone")
            if "timezone" in event_payload
            else (existing_event.get("timezone") if existing_event is not None else None)
        ),
        "all_day": (
            event_payload.get("all_day")
            if "all_day" in event_payload
            else (existing_event.get("all_day") if existing_event is not None else False)
        ),
        "organizer": (
            event_payload.get("organizer")
            if "organizer" in event_payload
            else (existing_event.get("organizer") if existing_event is not None else None)
        ),
        "attendee_count": len(attendees),
        "attendees": attendees,
        "has_alarms": bool(alarms),
        "recurrence": (
            event_payload.get("recurrence")
            if "recurrence" in event_payload
            else (existing_event.get("recurrence") if existing_event is not None else None)
        ),
        "alarms": alarms,
        "raw_ics": (
            event_payload.get("raw_ics")
            if "raw_ics" in event_payload
            else (existing_event.get("raw_ics") if existing_event is not None else None)
        ),
    }


def _event_overlaps_window(
    event: JSONDict,
    *,
    window_start_ms: int,
    window_end_ms: int,
) -> bool:
    start_at_ms = event.get("start_at_ms")
    end_at_ms = event.get("end_at_ms")
    if not isinstance(start_at_ms, int) or not isinstance(end_at_ms, int):
        return False
    return start_at_ms < window_end_ms and end_at_ms > window_start_ms


def _event_search_blob(event: JSONDict) -> str:
    fragments: list[str] = []
    for key in ("summary", "location"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            fragments.append(value.strip().lower())
    fragments.append(_organizer_blob(event))
    return "\n".join(fragment for fragment in fragments if fragment)


def _organizer_blob(event: JSONDict) -> str:
    organizer_value = event.get("organizer")
    if not isinstance(organizer_value, dict):
        return ""
    fragments: list[str] = []
    for key in ("email", "name"):
        value = organizer_value.get(key)
        if isinstance(value, str) and value.strip():
            fragments.append(value.strip().lower())
    return "\n".join(fragments)


def _attendee_blob(event: JSONDict) -> str:
    attendees_value = event.get("attendees")
    if not isinstance(attendees_value, list):
        return ""
    fragments: list[str] = []
    for attendee in attendees_value:
        if not isinstance(attendee, dict):
            continue
        address_value = attendee.get("address")
        if isinstance(address_value, dict):
            for key in ("email", "name"):
                value = address_value.get(key)
                if isinstance(value, str) and value.strip():
                    fragments.append(value.strip().lower())
    return "\n".join(fragments)
