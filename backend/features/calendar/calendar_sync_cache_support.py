"""SoAI - Calendar sync cache persistence support [backend/features/calendar/calendar_sync_cache_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.calendar.calendar_caldav_client import read_calendar_window_events
from features.calendar.calendar_event_cache import sync_window_events_to_cache
from features.calendar.calendar_record_context import require_calendar_remote_href
from features.calendar.calendar_sync_warning_support import append_sync_warning

if TYPE_CHECKING:
    import httpx2

    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.config.protocols import ConfigProtocol
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )
    from features.calendar.internal_protocols import CalendarSyncServiceProtocol

__all__ = (
    "sync_calendar_window_cache",
    "sync_service_calendar_window_cache",
    "update_account_sync_status",
    "upsert_discovered_calendars",
)

OPERATION = "features.calendar.calendar_sync_cache_support"
LOGGER_NAME = "SoAI.features.calendar.calendar_sync_cache_support"


async def upsert_discovered_calendars(
    *,
    database_calendar: DatabaseCalendarProtocol,
    user_id: int,
    account_id: str,
    discovery: JSONDict,
) -> list[JSONDict]:
    calendars_value = discovery.get("calendars")
    calendars = calendars_value if isinstance(calendars_value, list) else []
    stored_calendars: list[JSONDict] = []
    for calendar_entry in calendars:
        if not isinstance(calendar_entry, dict):
            continue
        stored_calendars.append(
            await database_calendar.upsert_calendar(
                user_id=user_id,
                account_id=account_id,
                payload=calendar_entry,
            ),
        )
    return stored_calendars


async def sync_calendar_window_cache(
    *,
    database_calendar: DatabaseCalendarProtocol,
    http_client: httpx2.AsyncClient,
    config: ConfigProtocol,
    prepared: PreparedCalendarTransportContext,
    user_id: int,
    account_id: str,
    calendar_row: JSONDict,
    window_start_ms: int,
    window_end_ms: int,
) -> JSONDict:
    remote_entries = await read_calendar_window_events(
        http_client=http_client,
        prepared=prepared,
        calendar_href=require_calendar_remote_href(calendar_row),
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
    )
    sync_result = await sync_window_events_to_cache(
        database_calendar=database_calendar,
        user_id=user_id,
        account_id=account_id,
        calendar_id=str(calendar_row["id"]),
        remote_entries=remote_entries,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        max_expansions_per_event=max(
            1,
            int(config.get_int("INTEGRATIONS.CALENDAR.RECURRENCE.MAX_EXPANSIONS_PER_EVENT")),
        ),
    )
    try:
        await database_calendar.replace_sync_window(
            calendar_id=str(calendar_row["id"]),
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            synced_at_ms=epoch_ms(),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            _calendar_sync_support_logger(),
            exception,
            message="Failed to persist calendar sync window metadata.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "calendar_id": str(calendar_row.get("id"))},
        )
        warning_reason = project_public_exception(exception).message
        append_sync_warning(
            sync_result,
            f"Calendar sync updated the local event cache, but SoAI could not persist the synced window metadata: {warning_reason}",
        )
    return sync_result


async def sync_service_calendar_window_cache(
    *,
    service: CalendarSyncServiceProtocol,
    prepared: PreparedCalendarTransportContext,
    user_id: int,
    account_id: str,
    calendar_row: JSONDict,
    window_start_ms: int,
    window_end_ms: int,
) -> JSONDict:
    return await sync_calendar_window_cache(
        database_calendar=service.database_calendar,
        http_client=service.http_client,
        config=service.config,
        prepared=prepared,
        user_id=user_id,
        account_id=account_id,
        calendar_row=calendar_row,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
    )


async def update_account_sync_status(
    *,
    database_calendar: DatabaseCalendarProtocol,
    user_id: int,
    account_id: str,
    sync_started_at_ms: int,
    error_message: str | None,
) -> None:
    updates: JSONDict = {"last_sync_error": error_message}
    if error_message is None:
        updates["last_sync_at_ms"] = sync_started_at_ms
    await database_calendar.update_account(
        user_id=user_id,
        account_id=account_id,
        updates=updates,
    )


def _calendar_sync_support_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
