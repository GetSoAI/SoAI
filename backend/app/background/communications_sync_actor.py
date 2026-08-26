"""SoAI - Background communications sync actor [backend/app/background/communications_sync_actor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.background.communications_sync_actor_iterations import (
    run_calendar_sync_iteration,
    run_mail_sync_iteration,
)
from app.background.communications_sync_actor_reminders import (
    run_calendar_reminder_iteration,
)
from app.background.communications_sync_actor_support import SyncBackoffState
from core.config.clamped_numeric import read_config_int_min_clamped
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.licensing.admission import LicensingOperationClass
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import (
    await_background_task_shutdown,
    run_background_periodic_task,
)
from core.timing.constants import BACKGROUND_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.calendar.protocols import (
        CalendarServiceProtocol,
        DatabaseCalendarProtocol,
    )
    from core.config.protocols import ConfigProtocol
    from core.external_accounts.protocols import LinkedAccountQueryProtocol
    from core.licensing.protocols import LicensingStatusProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.mcp.protocols_main import MCPServerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from core.users.protocols_database import DatabaseUsersProtocol

__all__ = (
    "CommunicationsSyncActor",
    "CommunicationsSyncActorDependencies",
)

LOGGER_NAME = "SoAI.app.background.communications_sync_actor"
OPERATION = "app.background.communications_sync_actor.run"


@dataclass(frozen=True, slots=True)
class CommunicationsSyncActorDependencies:
    config: ConfigProtocol
    database_users: DatabaseUsersProtocol
    database_calendar: DatabaseCalendarProtocol
    database_notifications: DatabaseNotificationsProtocol
    mail: MailServiceProtocol
    calendar: CalendarServiceProtocol
    mail_account_queries: LinkedAccountQueryProtocol
    calendar_account_queries: LinkedAccountQueryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="CommunicationsSyncActorDependencies",
            config=self.config,
            database_users=self.database_users,
            database_calendar=self.database_calendar,
            database_notifications=self.database_notifications,
            mail=self.mail,
            calendar=self.calendar,
            mail_account_queries=self.mail_account_queries,
            calendar_account_queries=self.calendar_account_queries,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
        )


class CommunicationsSyncActor:
    def __init__(self, deps: CommunicationsSyncActorDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._mail_task: asyncio.Task[None] | None = None
        self._calendar_task: asyncio.Task[None] | None = None
        self._reminder_task: asyncio.Task[None] | None = None
        self._mcp_server: MCPServerProtocol | None = None
        self._licensing_status: LicensingStatusProtocol | None = None
        self._mail_backoff_state: dict[str, SyncBackoffState] = {}
        self._calendar_backoff_state: dict[str, SyncBackoffState] = {}

    def attach_mcp_server(self, server: MCPServerProtocol | None) -> None:
        self._mcp_server = server

    def attach_licensing_status(self, licensing_status: LicensingStatusProtocol) -> None:
        self._licensing_status = licensing_status

    async def start(self) -> None:
        self._require_licensing_status()
        self._shutdown_event.clear()
        if self._mail_task is None or self._mail_task.done():
            self._mail_task = self._create_periodic_task(
                name="communications-mail-sync",
                interval_seconds=float(
                    read_config_int_min_clamped(
                        self._deps.config,
                        "INTEGRATIONS.MAIL.SYNC.INTERVAL_SEC",
                        0,
                        minimum=1,
                    ),
                ),
                task=self._run_mail_sync_iteration,
            )
        if self._calendar_task is None or self._calendar_task.done():
            self._calendar_task = self._create_periodic_task(
                name="communications-calendar-sync",
                interval_seconds=float(
                    read_config_int_min_clamped(
                        self._deps.config,
                        "INTEGRATIONS.CALENDAR.SYNC.INTERVAL_SEC",
                        0,
                        minimum=1,
                    ),
                ),
                task=self._run_calendar_sync_iteration,
            )
        if self._reminder_task is None or self._reminder_task.done():
            self._reminder_task = self._create_periodic_task(
                name="communications-calendar-reminders",
                interval_seconds=float(BACKGROUND_TIMEOUT_SEC),
                task=self._run_calendar_reminder_iteration,
            )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        await await_background_task_shutdown(
            self._mail_task,
            logger=self._logger,
            operation=f"{OPERATION}.shutdown_mail",
            message="Mail communications sync task failed during shutdown.",
            level="debug",
        )
        await await_background_task_shutdown(
            self._calendar_task,
            logger=self._logger,
            operation=f"{OPERATION}.shutdown_calendar",
            message="Calendar communications sync task failed during shutdown.",
            level="debug",
        )
        await await_background_task_shutdown(
            self._reminder_task,
            logger=self._logger,
            operation=f"{OPERATION}.shutdown_reminders",
            message="Calendar reminder task failed during shutdown.",
            level="debug",
        )
        self._mail_task = None
        self._calendar_task = None
        self._reminder_task = None
        self._mail_backoff_state.clear()
        self._calendar_backoff_state.clear()

    def _create_periodic_task(
        self,
        *,
        name: str,
        interval_seconds: float,
        task: Callable[[], Awaitable[None]],
    ) -> asyncio.Task[None]:
        return run_background_periodic_task(
            shutdown_event=self._shutdown_event,
            interval_seconds=interval_seconds,
            task=task,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="communications",
                owner=name,
                include_random_suffix=False,
            ),
            owner="communications_sync",
            name=name,
            logger=self._logger,
            metadata={"interval_ms": int(interval_seconds * 1000.0)},
            task_name=name.replace("-", "_"),
            run_immediately=True,
        )

    async def _run_mail_sync_iteration(self) -> None:
        if not await self._ordinary_operations_allowed():
            return
        await run_mail_sync_iteration(
            config=self._deps.config,
            database_users=self._deps.database_users,
            mail=self._deps.mail,
            account_queries=self._deps.mail_account_queries,
            logger=self._logger,
            mcp_server=self._mcp_server,
            backoff_state=self._mail_backoff_state,
        )

    async def _run_calendar_sync_iteration(self) -> None:
        if not await self._ordinary_operations_allowed():
            return
        await run_calendar_sync_iteration(
            config=self._deps.config,
            database_users=self._deps.database_users,
            calendar=self._deps.calendar,
            account_queries=self._deps.calendar_account_queries,
            logger=self._logger,
            mcp_server=self._mcp_server,
            backoff_state=self._calendar_backoff_state,
        )

    async def _run_calendar_reminder_iteration(self) -> None:
        if not await self._ordinary_operations_allowed():
            return
        await run_calendar_reminder_iteration(
            database_calendar=self._deps.database_calendar,
            database_notifications=self._deps.database_notifications,
            account_queries=self._deps.calendar_account_queries,
            logger=self._logger,
            mcp_server=self._mcp_server,
        )

    async def _ordinary_operations_allowed(self) -> bool:
        licensing_status = self._require_licensing_status()
        decision = await licensing_status.admission(LicensingOperationClass.ORDINARY)
        return decision.allowed

    def _require_licensing_status(self) -> LicensingStatusProtocol:
        if self._licensing_status is None:
            raise StateError("Communications licensing admission is not configured.")
        return self._licensing_status
