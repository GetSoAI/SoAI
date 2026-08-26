"""SoAI - Calendar event cache update helpers [backend/features/calendar/calendar_event_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.types.json import JSONDict
from core.validation.strings import coerce_trimmed_str_or_empty
from features.calendar.calendar_ics import parse_calendar_event_ics
from features.calendar.calendar_occurrences import event_has_window_occurrence
from features.calendar.calendar_reminder_sync import refresh_event_reminders

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol

__all__ = (
    "store_remote_calendar_event",
    "sync_window_events_to_cache",
)

OPERATION = "features.calendar.calendar_event_cache"
LOGGER_NAME = "SoAI.features.calendar.calendar_event_cache"


async def sync_window_events_to_cache(
    *,
    database_calendar: DatabaseCalendarProtocol,
    user_id: int,
    account_id: str,
    calendar_id: str,
    remote_entries: list[JSONDict],
    window_start_ms: int,
    window_end_ms: int,
    max_expansions_per_event: int,
) -> JSONDict:
    local_events = await database_calendar.list_events(user_id=user_id, calendar_id=calendar_id)
    local_by_remote_href = {
        remote_href: event
        for event in local_events
        if isinstance((remote_href := event.get("remote_href")), str) and remote_href.strip()
    }
    remote_hrefs: set[str] = set()
    imported_events_count = 0
    updated_events_count = 0
    imported_events: list[JSONDict] = []
    updated_events: list[JSONDict] = []
    warnings: list[str] = []
    for remote_entry in remote_entries:
        remote_href_value = remote_entry.get("remote_href")
        remote_href = coerce_trimmed_str_or_empty(remote_href_value)
        if not remote_href:
            continue
        remote_hrefs.add(remote_href)
        existing_event = local_by_remote_href.get(remote_href)
        stored_event, stored_warnings = await store_remote_calendar_event(
            database_calendar=database_calendar,
            user_id=user_id,
            account_id=account_id,
            calendar_id=calendar_id,
            remote_entry=remote_entry,
            existing_event=existing_event,
        )
        warnings.extend(stored_warnings)
        if existing_event is None:
            imported_events_count += 1
            imported_events.append(stored_event)
            continue
        if _event_changed(existing_event, stored_event):
            updated_events_count += 1
            updated_events.append(stored_event)
    deleted_events_count = 0
    for local_event in local_events:
        remote_href_value = local_event.get("remote_href")
        remote_href = coerce_trimmed_str_or_empty(remote_href_value)
        if not remote_href or remote_href in remote_hrefs:
            continue
        if not event_has_window_occurrence(
            event=local_event,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            max_expansions_per_event=max_expansions_per_event,
        ):
            continue
        event_id_value = local_event.get("id")
        event_id = coerce_trimmed_str_or_empty(event_id_value)
        if not event_id:
            continue
        deleted = await database_calendar.delete_event(user_id=user_id, event_id=event_id)
        if deleted:
            deleted_events_count += 1
    result: JSONDict = {
        "imported_events_count": imported_events_count,
        "updated_events_count": updated_events_count,
        "deleted_events_count": deleted_events_count,
        "imported_events": imported_events,
        "updated_events": updated_events,
    }
    if warnings:
        result["warnings"] = warnings
    return result


async def store_remote_calendar_event(
    *,
    database_calendar: DatabaseCalendarProtocol,
    user_id: int,
    account_id: str,
    calendar_id: str,
    remote_entry: JSONDict,
    existing_event: JSONDict | None,
) -> tuple[JSONDict, list[str]]:
    raw_ics_value = remote_entry.get("raw_ics")
    raw_ics = raw_ics_value if isinstance(raw_ics_value, str) else ""
    remote_href_value = remote_entry.get("remote_href")
    remote_href = coerce_trimmed_str_or_empty(remote_href_value)
    etag_value = remote_entry.get("etag")
    etag = etag_value.strip() if isinstance(etag_value, str) else None
    parsed_event = parse_calendar_event_ics(
        raw_ics=raw_ics,
        remote_href=remote_href,
        etag=etag,
    )
    if parsed_event is None:
        raise ValidationError("CalDAV calendar event payload is invalid.")
    stored_event = await database_calendar.upsert_event(
        user_id=user_id,
        calendar_id=calendar_id,
        payload=parsed_event,
    )
    warnings: list[str] = []
    if existing_event is None or _event_changed(existing_event, stored_event):
        try:
            await refresh_event_reminders(
                database_calendar=database_calendar,
                account_id=account_id,
                event=stored_event,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                _calendar_event_cache_logger(),
                exception,
                message="Failed to refresh calendar event reminders after cache update.",
                operation=OPERATION,
                level="warning",
                details={
                    "account_id": account_id,
                    "calendar_id": calendar_id,
                    "remote_href": remote_href,
                },
            )
            warning_reason = project_public_exception(exception).message
            warnings.append(
                f"Calendar event cache was updated, but SoAI could not refresh its reminders: {warning_reason}",
            )
    return stored_event, warnings


def _calendar_event_cache_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)


def _event_changed(existing_event: JSONDict, stored_event: JSONDict) -> bool:
    for key in (
        "etag",
        "uid",
        "summary",
        "description",
        "location",
        "start_at_ms",
        "end_at_ms",
        "updated_at_ms",
        "timezone",
        "all_day",
        "attendee_count",
        "has_alarms",
        "raw_ics",
    ):
        if existing_event.get(key) != stored_event.get(key):
            return True
    return (
        existing_event.get("organizer") != stored_event.get("organizer")
        or existing_event.get("attendees") != stored_event.get("attendees")
        or existing_event.get("recurrence") != stored_event.get("recurrence")
        or existing_event.get("alarms") != stored_event.get("alarms")
    )
