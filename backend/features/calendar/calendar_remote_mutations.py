"""SoAI - Calendar remote event mutation helpers [backend/features/calendar/calendar_remote_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.errors.public_projection import project_public_exception
from core.logging.trace import get_logger
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.calendar.calendar_caldav_client import (
    delete_remote_calendar_event,
    put_remote_calendar_event,
)
from features.calendar.calendar_event_support import (
    is_remote_calendar_href,
    require_id,
    resolve_existing_remote_event_href,
)
from features.calendar.calendar_ics import (
    build_calendar_event_ics,
    parse_calendar_event_ics,
)
from features.calendar.calendar_record_context import (
    load_event_row,
    require_calendar_remote_href,
    require_event_calendar_id,
    require_event_remote_href,
)
from features.calendar.calendar_reminder_sync import refresh_event_reminders

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )

__all__ = (
    "delete_calendar_event",
    "put_calendar_event",
)

OPERATION = "features.calendar.calendar_remote_mutations"
LOGGER_NAME = "SoAI.features.calendar.calendar_remote_mutations"


async def delete_calendar_event(
    *,
    database_calendar: DatabaseCalendarProtocol,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
    user_id: int,
    calendar_id: str,
    payload: JSONDict,
) -> JSONDict:
    event_id = require_id(payload.get("event_id"), "event_id is required for delete.")
    event_row = await load_event_row(
        database_calendar,
        user_id=user_id,
        event_id=event_id,
    )
    if require_event_calendar_id(event_row) != calendar_id:
        raise ValidationError("calendar_id does not match the event calendar.")
    remote_href = require_event_remote_href(event_row)
    if is_remote_calendar_href(remote_href):
        await delete_remote_calendar_event(
            http_client=http_client,
            prepared=prepared,
            event_href=remote_href,
            etag=coerce_optional_trimmed_str(event_row.get("etag")),
        )
    warnings: list[str] = []
    try:
        deleted = await database_calendar.delete_event(user_id=user_id, event_id=event_id)
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            _calendar_remote_mutations_logger(),
            exception,
            message="Failed to remove local calendar cache entry after remote delete.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "calendar_id": calendar_id, "event_id": event_id},
        )
        warning_reason = project_public_exception(exception).message
        warnings.append(
            f"Calendar event was deleted remotely, but SoAI could not remove the local cache entry: {warning_reason}",
        )
    else:
        if not deleted:
            warnings.append(
                "Calendar event was deleted remotely, but SoAI could not confirm the local cache removal.",
            )
    response: JSONDict = {"ok": True, "deleted": True, "event_id": event_id}
    if warnings:
        response["warnings"] = warnings
    return response


async def put_calendar_event(
    *,
    database_calendar: DatabaseCalendarProtocol,
    http_client: httpx2.AsyncClient,
    prepared: PreparedCalendarTransportContext,
    user_id: int,
    calendar_row: JSONDict,
    account_id: str,
    existing_event: JSONDict | None,
    event_payload: JSONDict,
) -> tuple[JSONDict, list[str]]:
    raw_ics, uid = build_calendar_event_ics(
        event_payload=event_payload,
        uid=(
            coerce_optional_trimmed_str(existing_event.get("uid"))
            if existing_event is not None
            else None
        ),
    )
    put_result = await put_remote_calendar_event(
        http_client=http_client,
        prepared=prepared,
        calendar_href=require_calendar_remote_href(calendar_row),
        event_href=resolve_existing_remote_event_href(existing_event),
        uid=uid,
        raw_ics=raw_ics,
        etag=(
            coerce_optional_trimmed_str(existing_event.get("etag"))
            if existing_event is not None
            else None
        ),
    )
    parsed_event = parse_calendar_event_ics(
        raw_ics=raw_ics,
        remote_href=str(put_result["remote_href"]),
        etag=coerce_optional_trimmed_str(put_result.get("etag")),
    )
    if parsed_event is None:
        raise ValidationError("CalDAV calendar event payload is invalid.")
    stored_event = await database_calendar.upsert_event(
        user_id=user_id,
        calendar_id=str(calendar_row["id"]),
        payload=parsed_event,
    )
    warnings: list[str] = []
    try:
        await refresh_event_reminders(
            event=stored_event,
            account_id=account_id,
            database_calendar=database_calendar,
        )
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            _calendar_remote_mutations_logger(),
            exception,
            message="Failed to refresh local reminders after remote calendar event save.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "calendar_id": str(calendar_row.get("id"))},
        )
        warning_reason = project_public_exception(exception).message
        warnings.append(
            f"Calendar event was saved, but SoAI could not finish local reminder synchronization: {warning_reason}",
        )
    return stored_event, warnings


def _calendar_remote_mutations_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
