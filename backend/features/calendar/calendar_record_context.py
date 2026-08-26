"""SoAI - Calendar record loading and relationship validation [backend/features/calendar/calendar_record_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.validation.strings import coerce_trimmed_str_or_empty

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.types.json import JSONDict

__all__ = (
    "load_calendar_row",
    "load_event_row",
    "require_calendar_account_id_from_row",
    "require_calendar_remote_href",
    "require_event_calendar_id",
    "require_event_remote_href",
)


async def load_calendar_row(
    database_calendar: DatabaseCalendarProtocol,
    *,
    user_id: int,
    calendar_id: str,
    missing_error: type[Exception],
    missing_message: str,
) -> JSONDict:
    calendar_row = await database_calendar.get_calendar(user_id=user_id, calendar_id=calendar_id)
    if calendar_row is None:
        raise missing_error(missing_message)
    return calendar_row


async def load_event_row(
    database_calendar: DatabaseCalendarProtocol,
    *,
    user_id: int,
    event_id: str,
    missing_error: type[Exception] = ValidationError,
    missing_message: str = "Calendar event not found.",
) -> JSONDict:
    event_row = await database_calendar.get_event(user_id=user_id, event_id=event_id)
    if event_row is None:
        raise missing_error(missing_message)
    return event_row


def require_calendar_account_id_from_row(calendar_row: JSONDict) -> str:
    account_id = coerce_trimmed_str_or_empty(calendar_row.get("calendar_account_id"))
    if not account_id:
        raise StateError("Calendar is missing its account id.")
    return account_id


def require_event_calendar_id(event_row: JSONDict) -> str:
    calendar_id = coerce_trimmed_str_or_empty(event_row.get("calendar_id"))
    if not calendar_id:
        raise StateError("Calendar event is missing its calendar id.")
    return calendar_id


def require_calendar_remote_href(calendar_row: JSONDict) -> str:
    remote_href = coerce_trimmed_str_or_empty(calendar_row.get("remote_href"))
    if not remote_href:
        raise StateError("Calendar is missing its remote href.")
    return remote_href


def require_event_remote_href(event_row: JSONDict) -> str:
    remote_href = coerce_trimmed_str_or_empty(event_row.get("remote_href"))
    if not remote_href:
        raise StateError("Calendar event is missing its remote href.")
    return remote_href
