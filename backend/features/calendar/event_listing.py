"""SoAI - Calendar event listing helpers [backend/features/calendar/event_listing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.durations import days_to_ms
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol

__all__ = (
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
