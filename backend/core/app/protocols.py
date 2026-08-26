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
)

if TYPE_CHECKING:
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
