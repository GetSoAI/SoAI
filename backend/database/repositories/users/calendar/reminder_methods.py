"""SoAI - Calendar repository reminder methods [backend/database/repositories/users/calendar/reminder_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.flags import FEATURE_AUTH
from database.repositories.users.calendar.record_normalization import (
    normalize_reminder_row,
)
from database.repositories.users.calendar.reminders import (
    read_due_calendar_reminders,
    sync_delete_calendar_event_reminders,
    sync_mark_calendar_reminder_delivered,
    sync_upsert_calendar_reminder,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.calendar.internal_protocols import (
        DatabaseCalendarCoreOwnerProtocol,
    )

__all__ = (
    "delete_event_reminders_method",
    "list_due_reminders_method",
    "mark_reminder_delivered_method",
    "upsert_reminder_method",
)


async def upsert_reminder_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    payload: JSONDict,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_upsert_calendar_reminder,
        payload,
    )
    normalized = normalize_reminder_row(row)
    if normalized is None:
        raise StateError("Calendar reminder is invalid.")
    return normalized


async def list_due_reminders_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    due_at_ms: int,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await self.core.reader.execute_read(read_due_calendar_reminders, due_at_ms=due_at_ms)
    return [normalized for row in rows if (normalized := normalize_reminder_row(row))]


async def delete_event_reminders_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    event_id: str,
) -> int:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    deleted_count = await self.core.writer.queue_write_operation(
        sync_delete_calendar_event_reminders,
        event_id,
    )
    return int(deleted_count) if isinstance(deleted_count, int) else 0


async def mark_reminder_delivered_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    reminder_id: str,
    delivered_at_ms: int,
) -> bool:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    return bool(
        await self.core.writer.queue_write_operation(
            sync_mark_calendar_reminder_delivered,
            reminder_id,
            delivered_at_ms,
        ),
    )
