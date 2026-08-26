"""SoAI - Calendar alarm value normalization [backend/features/calendar/calendar_alarm_values.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int
from features.calendar.calendar_ics_values import optional_ics_text

__all__ = (
    "DEFAULT_ALARM_ACTION",
    "CalendarAlarmValue",
    "calendar_alarm_to_payload",
    "normalize_alarm_entries",
    "normalize_alarm_entry",
    "parse_alarm_trigger_minutes",
)

DEFAULT_ALARM_ACTION = "DISPLAY"


@dataclass(frozen=True, slots=True)
class CalendarAlarmValue:
    trigger_minutes_before: int
    action: str
    description: str | None


def parse_alarm_trigger_minutes(trigger: timedelta | None) -> int | None:
    if trigger is None:
        return None
    return int(abs(trigger.total_seconds()) // 60)


def normalize_alarm_entries(value: JSONValue) -> list[CalendarAlarmValue]:
    if not isinstance(value, list):
        return []
    alarms: list[CalendarAlarmValue] = []
    for entry in value:
        alarm = normalize_alarm_entry(entry)
        if alarm is not None:
            alarms.append(alarm)
    return alarms


def normalize_alarm_entry(value: JSONValue) -> CalendarAlarmValue | None:
    if not isinstance(value, dict):
        return None
    minutes_value = value.get("trigger_minutes_before")
    if not is_strict_int(minutes_value):
        return None
    return CalendarAlarmValue(
        trigger_minutes_before=max(minutes_value, 0),
        action=optional_ics_text(value.get("action")) or DEFAULT_ALARM_ACTION,
        description=optional_ics_text(value.get("description")),
    )


def calendar_alarm_to_payload(alarm: CalendarAlarmValue) -> JSONDict:
    return {
        "trigger_minutes_before": alarm.trigger_minutes_before,
        "action": alarm.action,
        "description": alarm.description,
    }
