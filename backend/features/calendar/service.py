"""SoAI - Calendar domain service [backend/features/calendar/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import override

from core.calendar.protocols import CalendarServiceProtocol
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.types.json import JSONDict
from features.calendar.dependencies import CalendarServiceDependencies
from features.calendar.mutation_methods import (
    respond_to_invite_method,
    sync_account_method,
    sync_window_method,
    update_event_method,
)
from features.calendar.query_methods import (
    list_calendars_method,
    list_events_method,
    read_event_method,
)
from features.external_accounts.account_locking import bind_account_lock

__all__ = ("CalendarService",)


class CalendarService(CalendarServiceProtocol):
    def __init__(self, deps: CalendarServiceDependencies) -> None:
        self.config = deps.config
        self.runtime_flags = deps.runtime_flags
        self.event_bus = deps.event_bus
        self.http_client = deps.http_client
        self.database_calendar = deps.database_calendar
        self.database_mail = deps.database_mail
        self.database_notifications = deps.database_notifications
        self.external_accounts = deps.external_accounts
        self.mail_blocking_pool = deps.mail_blocking_pool
        self._account_locks: AsyncLockRegistryProtocol[tuple[int, str]] = (
            deps.calendar_account_locks
        )
        self._mail_account_locks: AsyncLockRegistryProtocol[tuple[int, str]] = (
            deps.mail_account_locks
        )
        self.account_lock = bind_account_lock(
            self._account_locks,
            label="account_id",
        )
        self.mail_account_lock = bind_account_lock(
            self._mail_account_locks,
            label="account_id",
        )

    @override
    async def sync_account(self, *, user_id: int, account_id: str) -> JSONDict:
        return await sync_account_method(self, user_id=user_id, account_id=account_id)

    @override
    async def sync_window(
        self,
        *,
        user_id: int,
        calendar_id: str,
        window_start_ms: int,
        window_end_ms: int,
    ) -> JSONDict:
        return await sync_window_method(
            self,
            user_id=user_id,
            calendar_id=calendar_id,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        )

    @override
    async def list_calendars(
        self,
        *,
        user_id: int,
        account_id: str,
        arguments: JSONDict,
    ) -> JSONDict:
        return await list_calendars_method(
            self,
            user_id=user_id,
            account_id=account_id,
            arguments=arguments,
        )

    @override
    async def list_events(self, *, user_id: int, calendar_id: str, arguments: JSONDict) -> JSONDict:
        return await list_events_method(
            self,
            user_id=user_id,
            calendar_id=calendar_id,
            arguments=arguments,
        )

    @override
    async def read_event(
        self,
        *,
        user_id: int,
        event_id: str,
        max_chars: int,
        offset_chars: int,
    ) -> JSONDict:
        return await read_event_method(
            self,
            user_id=user_id,
            event_id=event_id,
            max_chars=max_chars,
            offset_chars=offset_chars,
        )

    @override
    async def update_event(self, *, user_id: int, payload: JSONDict) -> JSONDict:
        return await update_event_method(self, user_id=user_id, payload=payload)

    @override
    async def respond_to_invite(
        self,
        *,
        user_id: int,
        event_id: str,
        action: str,
        comment: str | None,
    ) -> JSONDict:
        return await respond_to_invite_method(
            self,
            user_id=user_id,
            event_id=event_id,
            action=action,
            comment=comment,
        )
