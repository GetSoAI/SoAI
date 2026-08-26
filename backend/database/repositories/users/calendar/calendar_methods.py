"""SoAI - Calendar repository service methods [backend/database/repositories/users/calendar/calendar_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.core.flags import FEATURE_AUTH
from database.repositories.users.calendar.calendars import (
    read_calendar,
    read_calendars,
    sync_upsert_calendar,
)
from database.repositories.users.calendar.record_normalization import (
    normalize_calendar_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.users.calendar.internal_protocols import (
        DatabaseCalendarCoreOwnerProtocol,
    )

__all__ = (
    "get_calendar_method",
    "list_calendars_method",
    "upsert_calendar_method",
)


async def upsert_calendar_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
    payload: JSONDict,
) -> JSONDict:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.writer.queue_write_operation(
        sync_upsert_calendar,
        user_id,
        account_id,
        payload,
    )
    normalized = normalize_calendar_row(row)
    if normalized is None:
        raise StateError("Calendar is invalid.")
    return normalized


async def list_calendars_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    account_id: str,
) -> list[JSONDict]:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    rows = await self.core.reader.execute_read(
        read_calendars,
        user_id=user_id,
        account_id=account_id,
    )
    return [normalized for row in rows if (normalized := normalize_calendar_row(row))]


async def get_calendar_method(
    self: DatabaseCalendarCoreOwnerProtocol,
    *,
    user_id: int,
    calendar_id: str,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_AUTH)
    row = await self.core.reader.execute_read(
        read_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
    )
    return normalize_calendar_row(row)
