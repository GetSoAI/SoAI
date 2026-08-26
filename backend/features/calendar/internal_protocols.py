"""SoAI - Internal calendar service protocols [backend/features/calendar/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import httpx2

from core.concurrency.protocols import AsyncContextManagerProtocol

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.concurrency.bounded_blocking import BoundedBlockingPool
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.mail.protocols import DatabaseMailProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "CalendarAccountDomainServiceProtocol",
    "CalendarAccountLockProviderProtocol",
    "CalendarAccountTestingServiceProtocol",
    "CalendarDateTimePropertyProtocol",
    "CalendarDateTimesPropertyProtocol",
    "CalendarMutationServiceProtocol",
    "CalendarPropertyParamsProtocol",
    "CalendarRemoteReadServiceProtocol",
    "CalendarSyncServiceProtocol",
    "LinkedMailAccountLockProviderProtocol",
)


class LinkedMailAccountLockProviderProtocol(Protocol):
    def mail_account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


class CalendarAccountLockProviderProtocol(Protocol):
    def account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


@runtime_checkable
class CalendarPropertyParamsProtocol(Protocol):
    @property
    def params(self) -> dict[str, str]: ...


@runtime_checkable
class CalendarDateTimePropertyProtocol(Protocol):
    @property
    def dt(self) -> date | datetime | timedelta | str: ...


@runtime_checkable
class CalendarDateTimesPropertyProtocol(Protocol):
    @property
    def dts(self) -> list[date | datetime | timedelta | str | CalendarDateTimePropertyProtocol]: ...


class CalendarAccountTestingServiceProtocol(CalendarAccountLockProviderProtocol, Protocol):
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_calendar: DatabaseCalendarProtocol
    external_accounts: ExternalAccountsServiceProtocol


class CalendarAccountDomainServiceProtocol(CalendarAccountTestingServiceProtocol, Protocol):
    database_calendar: DatabaseCalendarProtocol
    database_mail: DatabaseMailProtocol
    external_accounts: ExternalAccountsServiceProtocol

    def mail_account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


class CalendarMutationServiceProtocol(CalendarAccountLockProviderProtocol, Protocol):
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_calendar: DatabaseCalendarProtocol
    database_mail: DatabaseMailProtocol
    database_notifications: DatabaseNotificationsProtocol
    external_accounts: ExternalAccountsServiceProtocol
    mail_blocking_pool: BoundedBlockingPool

    def mail_account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


class CalendarRemoteReadServiceProtocol(Protocol):
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_calendar: DatabaseCalendarProtocol
    external_accounts: ExternalAccountsServiceProtocol

    def account_lock(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...


class CalendarSyncServiceProtocol(CalendarAccountLockProviderProtocol, Protocol):
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    http_client: httpx2.AsyncClient
    database_calendar: DatabaseCalendarProtocol
    database_notifications: DatabaseNotificationsProtocol
    external_accounts: ExternalAccountsServiceProtocol
