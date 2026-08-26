"""SoAI - Calendar ICS parsing helpers [backend/features/calendar/calendar_ics_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from icalendar import Event

from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.calendar.calendar_alarm_values import (
    DEFAULT_ALARM_ACTION,
    CalendarAlarmValue,
    calendar_alarm_to_payload,
    parse_alarm_trigger_minutes,
)
from features.calendar.calendar_ics_values import (
    event_value_to_epoch_ms,
    extract_timezone_name,
    normalize_attendee_status,
    optional_ics_text,
    parse_address_property,
    parse_rsvp,
)
from features.calendar.internal_protocols import (
    CalendarDateTimePropertyProtocol,
    CalendarDateTimesPropertyProtocol,
    CalendarPropertyParamsProtocol,
)

__all__ = ("parse_calendar_event_component",)

if TYPE_CHECKING:
    type CalendarParamsPropertyValue = (
        str | date | datetime | timedelta | CalendarPropertyParamsProtocol
    )
    type CalendarDateTimesPropertyValue = (
        str | date | datetime | timedelta | CalendarDateTimesPropertyProtocol
    )
else:
    CalendarParamsPropertyValue = str | date | datetime | timedelta
    CalendarDateTimesPropertyValue = str | date | datetime | timedelta


def parse_calendar_event_component(
    *,
    event: Event,
    raw_ics: str,
    remote_href: str,
    etag: str | None,
) -> JSONDict:
    start_value = event.decoded("DTSTART")
    end_value = event.decoded("DTEND") if event.get("DTEND") is not None else None
    all_day = isinstance(start_value, date) and not isinstance(start_value, datetime)
    start_at_ms = event_value_to_epoch_ms(start_value)
    end_at_ms = (
        event_value_to_epoch_ms(end_value)
        if isinstance(end_value, date | datetime)
        else start_at_ms + (86_400_000 if all_day else 0)
    )
    organizer_property = event.get("ORGANIZER")
    organizer_params = _read_property_params(organizer_property)
    organizer = parse_address_property(
        raw_value=str(organizer_property) if organizer_property is not None else None,
        common_name=organizer_params.get("CN"),
    )
    attendees = _parse_attendees(event)
    alarms = _parse_alarms(event)
    recurrence = _parse_recurrence(event)
    start_property = event.get("DTSTART")
    start_params = _read_property_params(start_property)
    timezone_name = extract_timezone_name(start_params.get("TZID"))
    updated_property = event.get("LAST-MODIFIED") or event.get("DTSTAMP")
    updated_value = _read_property_dt(updated_property)
    updated_at_ms = (
        event_value_to_epoch_ms(updated_value)
        if isinstance(updated_value, date | datetime)
        else epoch_ms()
    )
    return {
        "remote_href": remote_href,
        "etag": etag,
        "uid": optional_ics_text(event.get("UID")),
        "summary": optional_ics_text(event.get("SUMMARY")) or "",
        "description": optional_ics_text(event.get("DESCRIPTION")),
        "location": optional_ics_text(event.get("LOCATION")),
        "start_at_ms": start_at_ms,
        "end_at_ms": max(end_at_ms, start_at_ms),
        "updated_at_ms": updated_at_ms,
        "timezone": timezone_name,
        "all_day": all_day,
        "organizer": organizer,
        "attendee_count": len(attendees),
        "attendees": attendees,
        "has_alarms": bool(alarms),
        "recurrence": recurrence,
        "alarms": alarms,
        "raw_ics": raw_ics,
    }


def _parse_attendees(event: Event) -> list[JSONDict]:
    attendees_value: CalendarParamsPropertyValue | list[CalendarParamsPropertyValue] | None = (
        event.get("ATTENDEE")
    )
    if attendees_value is None:
        return []
    attendees_entries = attendees_value if isinstance(attendees_value, list) else [attendees_value]
    attendees: list[JSONDict] = []
    for attendee_property in attendees_entries:
        params = _read_property_params(attendee_property)
        address = parse_address_property(
            raw_value=str(attendee_property),
            common_name=params.get("CN"),
        )
        if address is None:
            continue
        attendees.append(
            {
                "address": address,
                "rsvp": parse_rsvp(params.get("RSVP")),
                "role": optional_ics_text(params.get("ROLE")),
                "status": normalize_attendee_status(params.get("PARTSTAT")),
            },
        )
    return attendees


def _parse_alarms(event: Event) -> list[JSONDict]:
    alarms: list[JSONDict] = []
    for component in event.subcomponents:
        if component.name != "VALARM":
            continue
        trigger_property = component.get("TRIGGER")
        trigger_value = _read_property_dt(trigger_property)
        trigger_minutes = (
            parse_alarm_trigger_minutes(trigger_value)
            if isinstance(trigger_value, timedelta)
            else None
        )
        if trigger_minutes is None:
            continue
        alarms.append(
            calendar_alarm_to_payload(
                CalendarAlarmValue(
                    trigger_minutes_before=trigger_minutes,
                    action=optional_ics_text(component.get("ACTION")) or DEFAULT_ALARM_ACTION,
                    description=optional_ics_text(component.get("DESCRIPTION")),
                ),
            ),
        )
    return alarms


def _parse_recurrence(event: Event) -> JSONDict | None:
    rrule_value = event.get("RRULE")
    exdate_value: CalendarDateTimesPropertyValue | list[CalendarDateTimesPropertyValue] | None = (
        event.get("EXDATE")
    )
    if rrule_value is None and exdate_value is None:
        return None
    exdates_ms: list[int] = []
    if exdate_value is not None:
        exdate_entries = exdate_value if isinstance(exdate_value, list) else [exdate_value]
        for exdate_entry in exdate_entries:
            for item in _read_property_dts(exdate_entry):
                event_value = _read_property_dt(item)
                if isinstance(event_value, date | datetime):
                    exdates_ms.append(event_value_to_epoch_ms(event_value))
    return {
        "rrule": (
            optional_ics_text(rrule_value.to_ical().decode("utf-8"))
            if rrule_value is not None
            else None
        ),
        "exdates_ms": exdates_ms,
    }


def _read_property_params(
    value: str | date | datetime | timedelta | CalendarPropertyParamsProtocol | None,
) -> dict[str, str | None]:
    if value is None:
        return {}
    if not isinstance(value, CalendarPropertyParamsProtocol):
        return {}
    params = value.params
    if not isinstance(params, dict):
        return {}
    normalized: dict[str, str | None] = {}
    for key, raw_value in params.items():
        if not isinstance(key, str):
            continue
        normalized_value = raw_value.strip() if isinstance(raw_value, str) else None
        normalized[key] = normalized_value or None
    return normalized


def _read_property_dt(
    value: str | date | datetime | timedelta | CalendarDateTimePropertyProtocol | None,
) -> date | datetime | timedelta | str | None:
    if value is None:
        return None
    if not isinstance(value, CalendarDateTimePropertyProtocol):
        return value if isinstance(value, str) else None
    dt_value = value.dt
    if isinstance(dt_value, date | datetime | timedelta | str):
        return dt_value
    return None


def _read_property_dts(
    value: str | date | datetime | timedelta | CalendarDateTimesPropertyProtocol | None,
) -> list[date | datetime | timedelta | str]:
    if value is None:
        return []
    if not isinstance(value, CalendarDateTimesPropertyProtocol):
        return []
    raw_dts = value.dts
    try:
        entries = list(raw_dts)
    except TypeError:
        return []
    normalized: list[date | datetime | timedelta | str] = []
    for entry in entries:
        if isinstance(entry, date | datetime | timedelta | str):
            normalized.append(entry)
            continue
        if not isinstance(entry, CalendarDateTimePropertyProtocol):
            continue
        dt_value = entry.dt
        if isinstance(dt_value, date | datetime | timedelta | str):
            normalized.append(dt_value)
    return normalized
