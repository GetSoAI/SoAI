"""SoAI - Calendar repository service [backend/database/repositories/users/calendar/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, override

from core.calendar.protocols import DatabaseCalendarProtocol
from core.types.json import JSONDict
from database.repositories.users.calendar.accounts import (
    read_calendar_account,
    read_calendar_accounts,
    sync_create_calendar_account,
    sync_delete_calendar_account,
    sync_update_calendar_account,
)
from database.repositories.users.calendar.calendar_methods import (
    get_calendar_method,
    list_calendars_method,
    upsert_calendar_method,
)
from database.repositories.users.calendar.event_methods import (
    delete_event_method,
    get_event_method,
    list_events_method,
    list_sync_windows_method,
    replace_sync_window_method,
    upsert_event_method,
)
from database.repositories.users.calendar.record_normalization import (
    normalize_calendar_account_row,
)
from database.repositories.users.calendar.reminder_methods import (
    delete_event_reminders_method,
    list_due_reminders_method,
    mark_reminder_delivered_method,
    upsert_reminder_method,
)
from database.repositories.users.domain_account_repository_methods import (
    create_repository_account,
    delete_repository_account,
    get_repository_account,
    list_repository_accounts,
    update_repository_account,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseCalendar",)


class DatabaseCalendar(DatabaseCalendarProtocol):
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self.core = deps.core
        self.config = deps.config

    @override
    async def list_accounts(self, *, user_id: int) -> list[JSONDict]:
        return await list_repository_accounts(
            self,
            user_id=user_id,
            read_accounts=read_calendar_accounts,
            normalize_row=normalize_calendar_account_row,
        )

    @override
    async def get_account(self, *, user_id: int, account_id: str) -> JSONDict | None:
        return await get_repository_account(
            self,
            user_id=user_id,
            account_id=account_id,
            read_account=read_calendar_account,
            normalize_row=normalize_calendar_account_row,
        )

    @override
    async def create_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        return await create_repository_account(
            self,
            user_id=user_id,
            external_account_id=external_account_id,
            payload=payload,
            create_account=sync_create_calendar_account,
            normalize_row=normalize_calendar_account_row,
            invalid_message="Created calendar account is invalid.",
        )

    @override
    async def update_account(
        self,
        *,
        user_id: int,
        account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None:
        return await update_repository_account(
            self,
            user_id=user_id,
            account_id=account_id,
            updates=updates,
            update_account=sync_update_calendar_account,
            normalize_row=normalize_calendar_account_row,
        )

    @override
    async def delete_account(self, *, user_id: int, account_id: str) -> bool:
        return await delete_repository_account(
            self,
            user_id=user_id,
            account_id=account_id,
            delete_account=sync_delete_calendar_account,
        )

    @override
    async def upsert_calendar(
        self,
        *,
        user_id: int,
        account_id: str,
        payload: JSONDict,
    ) -> JSONDict:
        return await upsert_calendar_method(
            self,
            user_id=user_id,
            account_id=account_id,
            payload=payload,
        )

    @override
    async def list_calendars(self, *, user_id: int, account_id: str) -> list[JSONDict]:
        return await list_calendars_method(self, user_id=user_id, account_id=account_id)

    @override
    async def get_calendar(self, *, user_id: int, calendar_id: str) -> JSONDict | None:
        return await get_calendar_method(self, user_id=user_id, calendar_id=calendar_id)

    @override
    async def upsert_event(self, *, user_id: int, calendar_id: str, payload: JSONDict) -> JSONDict:
        return await upsert_event_method(
            self,
            user_id=user_id,
            calendar_id=calendar_id,
            payload=payload,
        )

    @override
    async def list_events(self, *, user_id: int, calendar_id: str) -> list[JSONDict]:
        return await list_events_method(self, user_id=user_id, calendar_id=calendar_id)

    @override
    async def get_event(self, *, user_id: int, event_id: str) -> JSONDict | None:
        return await get_event_method(self, user_id=user_id, event_id=event_id)

    @override
    async def delete_event(self, *, user_id: int, event_id: str) -> bool:
        return await delete_event_method(self, user_id=user_id, event_id=event_id)

    @override
    async def replace_sync_window(
        self,
        *,
        calendar_id: str,
        window_start_ms: int,
        window_end_ms: int,
        synced_at_ms: int,
    ) -> None:
        await replace_sync_window_method(
            self,
            calendar_id=calendar_id,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
            synced_at_ms=synced_at_ms,
        )

    @override
    async def list_sync_windows(self, *, calendar_id: str) -> list[JSONDict]:
        return await list_sync_windows_method(self, calendar_id=calendar_id)

    @override
    async def upsert_reminder(self, *, payload: JSONDict) -> JSONDict:
        return await upsert_reminder_method(self, payload=payload)

    @override
    async def list_due_reminders(self, *, due_at_ms: int) -> list[JSONDict]:
        return await list_due_reminders_method(self, due_at_ms=due_at_ms)

    @override
    async def delete_event_reminders(self, *, event_id: str) -> int:
        return await delete_event_reminders_method(self, event_id=event_id)

    @override
    async def mark_reminder_delivered(self, *, reminder_id: str, delivered_at_ms: int) -> bool:
        return await mark_reminder_delivered_method(
            self,
            reminder_id=reminder_id,
            delivered_at_ms=delivered_at_ms,
        )
