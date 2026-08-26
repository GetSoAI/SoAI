"""SoAI - Browser tool internal protocols [backend/mcp/tools/browser/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Literal, Protocol

from playwright.async_api import HttpCredentials, Page

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.config.protocols import ConfigProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from mcp.tools.browser.playwright_runtime import PlaywrightBrowserRuntime
from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "BrowserPageProtocol",
    "BrowserSessionStoreProtocol",
    "BrowserWorkspaceRuntimeSessionsProtocol",
)


class BrowserPageProtocol(Protocol):
    def title(self) -> str | Awaitable[str]: ...

    def wait_for_load_state(
        self,
        state: Literal["domcontentloaded", "load", "networkidle"] | None = None,
        *,
        timeout: float | None = None,
    ) -> None | Awaitable[None]: ...

    def wait_for_timeout(self, timeout: float) -> None | Awaitable[None]: ...


class BrowserWorkspaceRuntimeSessionsProtocol(Protocol):
    def current_owner_key(self) -> str: ...

    def require_workspace_path(self, owner_key: str | None = None) -> str: ...


class BrowserSessionStoreProtocol(Protocol):
    config: ConfigProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    sessions: dict[str, BrowserSessionState]
    sessions_lock: asyncio.Lock
    owner_create_locks: dict[str, asyncio.Lock]
    runtime: PlaywrightBrowserRuntime
    runtime_sessions: BrowserWorkspaceRuntimeSessionsProtocol
    storage_manager: StorageManagerProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    adblock_service: EasyListAdblockServiceProtocol | None
    SESSION_IDLE_TTL_SEC: float
    MAX_SESSIONS: int

    def current_owner_key(self) -> str: ...

    async def prune(self) -> None: ...

    async def close_owner_session(self, owner_key: str, *, persist: bool = True) -> None: ...

    async def shutdown(self) -> None: ...

    async def create_tab(self, state: BrowserSessionState) -> Page: ...

    async def get_or_create_session(
        self,
        *,
        owner_key: str,
        owner_base: str,
        profile: str,
        session_scope: str,
    ) -> BrowserSessionState: ...

    async def recreate_context(
        self,
        *,
        state: BrowserSessionState,
        http_credentials: HttpCredentials | None,
        ignore_https_errors: bool,
    ) -> None: ...
