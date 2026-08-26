"""SoAI - Calendar repository event methods [backend/database/repositories/users/calendar/event_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.flags import FEATURE_AUTH
from database.repositories.users.calendar.events import (
    read_calendar_event,
    read_calendar_events,
    sync_delete_calendar_event,
    sync_upsert_calendar_event,
)
from database.repositories.users.calendar.record_normalization import (
    normalize_calendar_event_row,
    normalize_sync_window_row,
)
from database.repositories.users.calendar.sync_windows import (
    read_calendar_sync_windows,
    sync_replace_calendar_sync_window,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.calendar.internal_protocols import (
        DatabaseCalendarCoreOwnerProtocol,
    )

__all__ = (
    "delete_event_method",
    "get_event_method",
    "list_events_method",
    "list_sync_windows_method",
    "replace_sync_window_method",
    "upsert_event_method",
)


async def upsert_event_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    calendar_id: str,
    payload: JSONDict,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_upsert_calendar_event,
        user_id,
        calendar_id,
        payload,
    )
    normalized = normalize_calendar_event_row(row)
    if normalized is None:
        raise StateError("Calendar event is invalid.")
    return normalized


async def list_events_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    calendar_id: str,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await self.core.reader.execute_read(
        read_calendar_events,
        user_id=user_id,
        calendar_id=calendar_id,
    )
    return [normalized for row in rows if (normalized := normalize_calendar_event_row(row))]


async def get_event_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    event_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_calendar_event,
        user_id=user_id,
        event_id=event_id,
    )
    return normalize_calendar_event_row(row)


async def delete_event_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    event_id: str,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return bool(
        await self.core.writer.queue_write_operation(
            sync_delete_calendar_event,
            user_id,
            event_id,
        ),
    )


async def replace_sync_window_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    calendar_id: str,
    window_start_ms: int,
    window_end_ms: int,
    synced_at_ms: int,
) -> None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    await self.core.writer.queue_write_operation(
        sync_replace_calendar_sync_window,
        calendar_id,
        window_start_ms,
        window_end_ms,
        synced_at_ms,
    )


async def list_sync_windows_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    calendar_id: str,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await self.core.reader.execute_read(read_calendar_sync_windows, calendar_id=calendar_id)
    return [normalized for row in rows if (normalized := normalize_sync_window_row(row))]
