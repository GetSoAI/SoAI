"""SoAI - Calendar service dependencies [backend/features/calendar/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

import httpx2

from core.calendar.protocols import DatabaseCalendarProtocol
from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.external_accounts.protocols import ExternalAccountsServiceProtocol
from core.mail.protocols import DatabaseMailProtocol
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = ("CalendarServiceDependencies",)


@dataclass(frozen=True, slots=True)
class CalendarServiceDependencies:
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    event_bus: EventBusProtocol
    http_client: httpx2.AsyncClient
    database_calendar: DatabaseCalendarProtocol
    database_mail: DatabaseMailProtocol
    database_notifications: DatabaseNotificationsProtocol
    external_accounts: ExternalAccountsServiceProtocol
    mail_blocking_pool: BoundedBlockingPool
    calendar_account_locks: AsyncLockRegistryProtocol[tuple[int, str]]
    mail_account_locks: AsyncLockRegistryProtocol[tuple[int, str]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CalendarServiceDependencies",
            config=self.config,
            runtime_flags=self.runtime_flags,
            event_bus=self.event_bus,
            http_client=self.http_client,
            database_calendar=self.database_calendar,
            database_mail=self.database_mail,
            database_notifications=self.database_notifications,
            external_accounts=self.external_accounts,
            mail_blocking_pool=self.mail_blocking_pool,
            calendar_account_locks=self.calendar_account_locks,
            mail_account_locks=self.mail_account_locks,
        )
