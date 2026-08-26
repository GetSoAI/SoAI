"""SoAI - Browser session store [backend/mcp/tools/browser/session_store.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import contextvars
from typing import TYPE_CHECKING

from playwright.async_api import HttpCredentials, Page

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.hardware.protocols_storage import StorageManagerProtocol
from mcp.tools.browser.internal_protocols import BrowserWorkspaceRuntimeSessionsProtocol
from mcp.tools.browser.playwright_runtime import PlaywrightBrowserRuntime
from mcp.tools.browser.session_state import mark_browser_session_driver_disconnected
from mcp.tools.browser.session_store_create import (
    create_tab,
    get_or_create_session,
)
from mcp.tools.browser.session_store_lifecycle import (
    close_owner_session,
    prune,
)
from mcp.tools.browser.session_store_recreate import (
    recreate_context,
)
from mcp.tools.browser.session_store_shutdown import (
    shutdown,
)
from mcp.tools.browser.types import BrowserSessionState

if TYPE_CHECKING:
    from core.runtime.protocols import RuntimeFlagsViewProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )

__all__ = ("BrowserSessionStore",)


class BrowserSessionStore:
    SESSION_IDLE_TTL_SEC: float = 3600.0
    MAX_SESSIONS: int = 256

    def __init__(
        self,
        *,
        config: ConfigProtocol,
        runtime_flags: RuntimeFlagsViewProtocol,
        active_client_context: contextvars.ContextVar[str | None],
        runtime_sessions: BrowserWorkspaceRuntimeSessionsProtocol,
        storage_manager: StorageManagerProtocol,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        adblock_service: EasyListAdblockServiceProtocol | None = None,
    ) -> None:
        if config is None:
            raise ValidationError("Config is required for BrowserSessionStore.")
        if runtime_flags is None:
            raise ValidationError("runtime_flags is required for BrowserSessionStore.")
        if active_client_context is None:
            raise ValidationError("active_client_context is required for BrowserSessionStore.")
        if runtime_sessions is None:
            raise ValidationError("runtime_sessions is required for BrowserSessionStore.")
        if storage_manager is None:
            raise ValidationError("storage_manager is required for BrowserSessionStore.")
        if cancellation_binder is None:
            raise ValidationError("cancellation_binder is required for BrowserSessionStore.")
        if finalizer_tracker is None:
            raise ValidationError("finalizer_tracker is required for BrowserSessionStore.")
        self.config = config
        self.runtime_flags = runtime_flags
        self._active_client_context = active_client_context
        self.runtime_sessions = runtime_sessions
        self.storage_manager = storage_manager
        self.cancellation_binder = cancellation_binder
        self.finalizer_tracker = finalizer_tracker
        self.adblock_service = adblock_service
        self.sessions: dict[str, BrowserSessionState] = {}
        self.sessions_lock = asyncio.Lock()
        self.owner_create_locks: dict[str, asyncio.Lock] = {}
        self.runtime = PlaywrightBrowserRuntime(
            config=config,
            runtime_flags=runtime_flags,
            driver_disconnect_notifier=self._mark_driver_disconnected_sessions,
        )

    def current_owner_key(self) -> str:
        value = self._active_client_context.get()
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "default"

    async def prune(self) -> None:
        await prune(self)

    async def create_tab(self, state: BrowserSessionState) -> Page:
        return await create_tab(self, state)

    async def get_or_create_session(
        self,
        *,
        owner_key: str,
        owner_base: str,
        profile: str,
        session_scope: str,
    ) -> BrowserSessionState:
        return await get_or_create_session(
            self,
            owner_key=owner_key,
            owner_base=owner_base,
            profile=profile,
            session_scope=session_scope,
        )

    async def recreate_context(
        self,
        *,
        state: BrowserSessionState,
        http_credentials: HttpCredentials | None,
        ignore_https_errors: bool,
    ) -> None:
        await recreate_context(
            self,
            state=state,
            http_credentials=http_credentials,
            ignore_https_errors=ignore_https_errors,
        )

    async def close_owner_session(
        self,
        owner_key: str,
        *,
        persist: bool = True,
    ) -> None:
        await close_owner_session(self, owner_key, persist=persist)

    async def shutdown(self) -> None:
        await shutdown(self)

    async def _mark_driver_disconnected_sessions(self) -> None:
        async with self.sessions_lock:
            states = list(self.sessions.values())
        for state in states:
            mark_browser_session_driver_disconnected(
                state,
                reason="Playwright driver connection closed while the browser session was active.",
            )
