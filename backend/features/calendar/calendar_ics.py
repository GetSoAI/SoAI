"""SoAI - Calendar ICS parsing and generation [backend/features/calendar/calendar_ics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import timedelta

from icalendar import Alarm, Calendar, Event

from core.errors.exceptions import ValidationError
from core.timing.formatting import utc_now
from core.types.json import JSONDict
from features.calendar.calendar_alarm_values import normalize_alarm_entries
from features.calendar.calendar_ics_parsing import parse_calendar_event_component
from features.calendar.calendar_ics_values import (
    build_address_property,
    encode_attendee_status,
    optional_ics_text,
    require_event_text,
    require_event_timestamp,
    resolve_event_uid,
    timestamp_to_event_value,
)

__all__ = (
    "build_calendar_event_ics",
    "parse_calendar_event_ics",
)


def parse_calendar_event_ics(
    *,
    raw_ics: str,
    remote_href: str,
    etag: str | None,
) -> JSONDict | None:
    calendar = Calendar.from_ical(raw_ics)
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue
        if not isinstance(component, Event):
            continue
        return parse_calendar_event_component(
            event=component,
            raw_ics=raw_ics,
            remote_href=remote_href,
            etag=etag,
        )
    return None


def build_calendar_event_ics(
    *,
    event_payload: JSONDict,
    uid: str | None,
) -> tuple[str, str]:
    calendar = Calendar()
    calendar.add("prodid", "-//SoAI//Calendar//EN")
    calendar.add("version", "2.0")
    event = Event()
    event_uid = resolve_event_uid(event_payload, uid)
    summary = require_event_text(event_payload.get("summary"), "summary")
    event.add("uid", event_uid)
    event.add("summary", summary)
    now_dt = utc_now()
    event.add("dtstamp", now_dt)
    event.add("last-modified", now_dt)
    description = optional_ics_text(event_payload.get("description"))
    if description is not None:
        event.add("description", description)
    location = optional_ics_text(event_payload.get("location"))
    if location is not None:
        event.add("location", location)
    _add_event_time_range(event=event, event_payload=event_payload)
    organizer_value = event_payload.get("organizer")
    if isinstance(organizer_value, dict):
        organizer = build_address_property(organizer_value)
        if organizer is not None:
            event["organizer"] = organizer
    attendees_value = event_payload.get("attendees")
    if isinstance(attendees_value, list):
        for attendee_entry in attendees_value:
            if not isinstance(attendee_entry, dict):
                continue
            address_value = attendee_entry.get("address")
            if not isinstance(address_value, dict):
                continue
            attendee = build_address_property(address_value)
            if attendee is None:
                continue
            role = optional_ics_text(attendee_entry.get("role"))
            status = encode_attendee_status(optional_ics_text(attendee_entry.get("status")))
            rsvp_value = attendee_entry.get("rsvp")
            if role is not None:
                attendee.params["ROLE"] = role.upper()
            if status is not None:
                attendee.params["PARTSTAT"] = status
            if isinstance(rsvp_value, bool):
                attendee.params["RSVP"] = "TRUE" if rsvp_value else "FALSE"
            event.add("attendee", attendee, encode=False)
    recurrence_value = event_payload.get("recurrence")
    if isinstance(recurrence_value, dict):
        rrule_value = optional_ics_text(recurrence_value.get("rrule"))
        if rrule_value is not None:
            event.add("rrule", rrule_value)
        exdates_value = recurrence_value.get("exdates_ms")
        if isinstance(exdates_value, list):
            for entry in exdates_value:
                if isinstance(entry, int) and entry > 0:
                    event.add(
                        "exdate",
                        timestamp_to_event_value(
                            event_payload=event_payload,
                            timestamp_ms=entry,
                        ),
                    )
    for alarm_value in normalize_alarm_entries(event_payload.get("alarms")):
        alarm = Alarm()
        alarm.add(
            "action",
            alarm_value.action,
        )
        alarm.add("trigger", timedelta(minutes=-alarm_value.trigger_minutes_before))
        alarm.add(
            "description",
            alarm_value.description or summary,
        )
        event.add_component(alarm)
    calendar.add_component(event)
    return (calendar.to_ical().decode("utf-8"), event_uid)


def _add_event_time_range(*, event: Event, event_payload: JSONDict) -> None:
    start_at_ms = require_event_timestamp(event_payload.get("start_at_ms"), "start_at_ms")
    end_at_ms = require_event_timestamp(event_payload.get("end_at_ms"), "end_at_ms")
    if end_at_ms < start_at_ms:
        raise ValidationError("end_at_ms must be greater than or equal to start_at_ms.")
    event.add(
        "dtstart",
        timestamp_to_event_value(event_payload=event_payload, timestamp_ms=start_at_ms),
    )
    event.add(
        "dtend",
        timestamp_to_event_value(event_payload=event_payload, timestamp_ms=end_at_ms),
    )
