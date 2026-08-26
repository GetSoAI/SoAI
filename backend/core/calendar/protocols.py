"""SoAI - Calendar service protocols [backend/core/calendar/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.external_accounts.protocols import LinkedDomainAccountStorageProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "CalendarServiceProtocol",
    "DatabaseCalendarProtocol",
)


class DatabaseCalendarProtocol(LinkedDomainAccountStorageProtocol, Protocol):
    async def upsert_calendar(
        self,
        *,
        user_id: int,
        account_id: str,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def list_calendars(self, *, user_id: int, account_id: str) -> list[JSONDict]: ...

    async def get_calendar(self, *, user_id: int, calendar_id: str) -> JSONDict | None: ...

    async def upsert_event(
        self,
        *,
        user_id: int,
        calendar_id: str,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def list_events(self, *, user_id: int, calendar_id: str) -> list[JSONDict]: ...

    async def get_event(self, *, user_id: int, event_id: str) -> JSONDict | None: ...

    async def delete_event(self, *, user_id: int, event_id: str) -> bool: ...

    async def replace_sync_window(
        self,
        *,
        calendar_id: str,
        window_start_ms: int,
        window_end_ms: int,
        synced_at_ms: int,
    ) -> None: ...

    async def list_sync_windows(self, *, calendar_id: str) -> list[JSONDict]: ...

    async def upsert_reminder(self, *, payload: JSONDict) -> JSONDict: ...

    async def list_due_reminders(self, *, due_at_ms: int) -> list[JSONDict]: ...

    async def delete_event_reminders(self, *, event_id: str) -> int: ...

    async def mark_reminder_delivered(
        self,
        *,
        reminder_id: str,
        delivered_at_ms: int,
    ) -> bool: ...


class CalendarServiceProtocol(Protocol):
    async def sync_account(self, *, user_id: int, account_id: str) -> JSONDict: ...

    async def sync_window(
        self,
        *,
        user_id: int,
        calendar_id: str,
        window_start_ms: int,
        window_end_ms: int,
    ) -> JSONDict: ...

    async def list_calendars(
        self,
        *,
        user_id: int,
        account_id: str,
        arguments: JSONDict,
    ) -> JSONDict: ...

    async def list_events(
        self,
        *,
        user_id: int,
        calendar_id: str,
        arguments: JSONDict,
    ) -> JSONDict: ...

    async def read_event(
        self,
        *,
        user_id: int,
        event_id: str,
        max_chars: int,
        offset_chars: int,
    ) -> JSONDict: ...

    async def update_event(self, *, user_id: int, payload: JSONDict) -> JSONDict: ...

    async def respond_to_invite(
        self,
        *,
        user_id: int,
        event_id: str,
        action: str,
        comment: str | None,
    ) -> JSONDict: ...
