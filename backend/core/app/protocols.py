"""SoAI - Core protocols for the app composition root [backend/core/app/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Literal, Protocol

__all__ = (
    "ApplicationControlProtocol",
    "ApplicationRuntimeCoordinatorProtocol",
    "BannerSystemProtocol",
    "CancellationSystemProtocol",
    "CommunicationsServicesProtocol",
    "CommunicationsSyncProtocol",
)

if TYPE_CHECKING:
    from core.calendar.protocols import CalendarServiceProtocol
    from core.external_accounts.linked_account_types import LinkedAccountCapabilities
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.licensing.protocols import LicensingStatusProtocol
    from core.mail.protocols import MailServiceProtocol
    from core.mcp.protocols_main import MCPServerProtocol
    from core.tasks.protocols import (
        CancellationCoordinatorProtocol,
        CancellationEventBusProtocol,
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TokenCollectionProtocol,
    )

    type ApplicationUpdateOutcome = Literal[
        "accepted",
        "conflict",
        "failed",
        "unavailable",
    ]


class BannerSystemProtocol(Protocol):
    def emit(self, key: str) -> None: ...


class ApplicationRuntimeCoordinatorProtocol(Protocol):
    def fail_startup(self, reason: str, exit_code: int = 1) -> None: ...

    def ensure_banner_system(self) -> BannerSystemProtocol: ...

    def get_configuration_flag(self, key: str, default: bool) -> bool: ...

    def schedule_background_task(
        self,
        coroutine: Coroutine[None, None, None],
        *,
        name: str | None = None,
    ) -> asyncio.Task[None] | None: ...

    def track_background_task(self, task: asyncio.Task[None]) -> None: ...


class ApplicationControlProtocol(Protocol):
    async def update(self) -> tuple[ApplicationUpdateOutcome, str]: ...

    def restart(self) -> bool: ...

    def request_shutdown(self, reason: str | None = None) -> bool: ...

    def schedule_background_task(
        self,
        coroutine: Coroutine[None, None, None],
        *,
        name: str | None = None,
    ) -> asyncio.Task[None] | None: ...

    def track_background_task(self, task: asyncio.Task[None]) -> None: ...


class CommunicationsSyncProtocol(Protocol):
    def attach_mcp_server(self, server: MCPServerProtocol | None) -> None: ...

    def attach_licensing_status(self, licensing_status: LicensingStatusProtocol) -> None: ...

    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...


class CommunicationsServicesProtocol(Protocol):
    @property
    def external_accounts(self) -> ExternalAccountsServiceProtocol: ...

    @property
    def mail(self) -> MailServiceProtocol: ...

    @property
    def calendar(self) -> CalendarServiceProtocol: ...

    @property
    def mail_accounts(self) -> LinkedAccountCapabilities: ...

    @property
    def calendar_accounts(self) -> LinkedAccountCapabilities: ...

    @property
    def sync_actor(self) -> CommunicationsSyncProtocol: ...


class CancellationSystemProtocol(Protocol):
    @property
    def token_collection(self) -> TokenCollectionProtocol: ...

    @property
    def history(self) -> CancellationHistoryProtocol: ...

    @property
    def event_bus(self) -> CancellationEventBusProtocol: ...

    @property
    def finalizer_tracker(self) -> TaskFinalizerTrackerProtocol: ...

    @property
    def binder(self) -> TaskCancellationBinderProtocol: ...

    @property
    def coordinator(self) -> CancellationCoordinatorProtocol: ...
