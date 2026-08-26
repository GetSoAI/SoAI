"""SoAI - Calendar remote event read helpers [backend/features/calendar/calendar_remote_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from features.calendar.calendar_caldav_client import read_remote_calendar_event
from features.calendar.calendar_caldav_context import prepare_calendar_transport_context
from features.calendar.calendar_event_cache import store_remote_calendar_event
from features.calendar.calendar_record_context import (
    load_calendar_row,
    load_event_row,
    require_calendar_account_id_from_row,
    require_event_calendar_id,
    require_event_remote_href,
)
from features.calendar.internal_protocols import CalendarRemoteReadServiceProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("refresh_remote_calendar_event_cache",)


async def refresh_remote_calendar_event_cache(
    service: CalendarRemoteReadServiceProtocol,
    *,
    user_id: int,
    event_id: str,
) -> tuple[JSONDict, list[str]]:
    if service.runtime_flags.offline_mode:
        raise ValidationError("Calendar event content is not cached and offline mode is enabled.")
    event = await load_event_row(
        service.database_calendar,
        user_id=user_id,
        event_id=event_id,
    )
    calendar_id = require_event_calendar_id(event)
    calendar_row = await load_calendar_row(
        service.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=StateError,
        missing_message="Calendar not found.",
    )
    account_id = require_calendar_account_id_from_row(calendar_row)
    require_event_remote_href(event)
    async with service.account_lock(user_id=user_id, account_id=account_id):
        locked_event = await load_event_row(
            service.database_calendar,
            user_id=user_id,
            event_id=event_id,
        )
        locked_calendar_id = require_event_calendar_id(locked_event)
        locked_calendar_row = await load_calendar_row(
            service.database_calendar,
            user_id=user_id,
            calendar_id=locked_calendar_id,
            missing_error=StateError,
            missing_message="Calendar not found.",
        )
        locked_account_id = require_calendar_account_id_from_row(locked_calendar_row)
        if locked_account_id != account_id:
            raise StateError("Calendar event account changed unexpectedly.")
        locked_remote_href = require_event_remote_href(locked_event)
        prepared = await prepare_calendar_transport_context(
            config=service.config,
            runtime_flags=service.runtime_flags,
            database_calendar=service.database_calendar,
            external_accounts=service.external_accounts,
            user_id=user_id,
            account_id=locked_account_id,
            validate_endpoint=True,
        )
        remote_entry = await read_remote_calendar_event(
            http_client=service.http_client,
            prepared=prepared,
            event_href=locked_remote_href,
        )
        return await store_remote_calendar_event(
            database_calendar=service.database_calendar,
            user_id=user_id,
            account_id=locked_account_id,
            calendar_id=locked_calendar_id,
            remote_entry=remote_entry,
            existing_event=locked_event,
        )
