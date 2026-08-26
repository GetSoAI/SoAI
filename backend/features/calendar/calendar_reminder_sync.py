"""SoAI - Calendar reminder scheduling [backend/features/calendar/calendar_reminder_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.users.user_id import is_strict_user_id
from core.validation.integers import is_strict_int
from features.calendar.calendar_alarm_values import normalize_alarm_entries

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.types.json import JSONDict

__all__ = (
    "refresh_event_reminders",
    "schedule_event_reminders",
)


async def refresh_event_reminders(
    *,
    database_calendar: DatabaseCalendarProtocol,
    account_id: str,
    event: JSONDict,
) -> None:
    event_id_value = event.get("id")
    event_id = event_id_value if isinstance(event_id_value, str) else ""
    if not event_id:
        return
    await database_calendar.delete_event_reminders(event_id=event_id)
    await schedule_event_reminders(
        database_calendar=database_calendar,
        account_id=account_id,
        event=event,
    )


async def schedule_event_reminders(
    *,
    database_calendar: DatabaseCalendarProtocol,
    account_id: str,
    event: JSONDict,
) -> None:
    start_at_value = event.get("start_at_ms")
    if not is_strict_int(start_at_value):
        return
    user_id_value = event.get("user_id")
    user_id = user_id_value if is_strict_user_id(user_id_value) else None
    event_id_value = event.get("id")
    event_id = event_id_value if isinstance(event_id_value, str) else ""
    if user_id is None or not event_id:
        return
    response_state = _resolve_response_state(event)
    for alarm in normalize_alarm_entries(event.get("alarms")):
        await database_calendar.upsert_reminder(
            payload={
                "user_id": user_id,
                "calendar_account_id": account_id,
                "event_id": event_id,
                "occurrence_key": str(start_at_value),
                "alarm_key": f"{alarm.action}:{alarm.trigger_minutes_before}",
                "response_state": response_state,
                "remind_at_ms": max(start_at_value - alarm.trigger_minutes_before * 60_000, 0),
                "due_at_ms": start_at_value,
            },
        )


def _resolve_response_state(event: JSONDict) -> str:
    attendees_value = event.get("attendees")
    if not isinstance(attendees_value, list):
        return "default"
    for attendee in attendees_value:
        if not isinstance(attendee, dict):
            continue
        status_value = attendee.get("status")
        if isinstance(status_value, str) and status_value.strip():
            return status_value.strip().lower()
    return "default"
