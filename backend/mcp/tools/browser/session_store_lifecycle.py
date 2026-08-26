"""SoAI - Browser session store lifecycle methods [backend/mcp/tools/browser/session_store_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from mcp.tools.browser.download_tasks import cancel_active_download_tasks
from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
from mcp.tools.browser.playwright_runtime_shutdown import (
    close_browser_context_with_logging,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.storage_state import (
    maybe_save_storage_state_for_session,
)
from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "close_browser_context",
    "close_owner_session",
    "prune",
    "touch_session_state",
)

LOGGER_NAME = "SoAI.mcp.tools.session_store_lifecycle"
OPERATION = "mcp.browser.session_store.close_context.release_profile_lock"
NONCRITICAL_PROFILE_LOCK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    RuntimeError,
    *RECOVERABLE_EXCEPTIONS,
)


def touch_session_state(state: BrowserSessionState) -> None:
    state.last_touched_monotonic = time.monotonic()


async def close_browser_context(state: BrowserSessionState, operation: str) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await close_browser_context_with_logging(
            state.context,
            logger=logger,
            operation=operation,
            details={"owner_key": state.owner_key},
        )
    finally:
        lock = state.profile_lock
        state.profile_lock = None
        if lock is not None:
            try:
                await asyncio.to_thread(lock.release)
            except NONCRITICAL_PROFILE_LOCK_EXCEPTIONS as exception:
                _log_noncritical_profile_lock_error(
                    logger,
                    exception,
                    owner_key=state.owner_key,
                )


async def prune(self: BrowserSessionStoreProtocol) -> None:
    now = time.monotonic()
    to_close: list[BrowserSessionState] = []
    async with self.sessions_lock:
        expired_keys: list[str] = []
        for owner_key, state in self.sessions.items():
            if state.lock.locked() or state.action_lock.locked():
                continue
            if (now - state.last_touched_monotonic) >= self.SESSION_IDLE_TTL_SEC:
                expired_keys.append(owner_key)
        for owner_key in expired_keys:
            expired_state = self.sessions.get(owner_key)
            if expired_state is None:
                continue
            self.sessions.pop(owner_key)
            to_close.append(expired_state)
        if len(self.sessions) > self.MAX_SESSIONS:
            lru = sorted(self.sessions.items(), key=lambda item: item[1].last_touched_monotonic)
            for owner_key, state in lru:
                if len(self.sessions) <= self.MAX_SESSIONS:
                    break
                if state.lock.locked() or state.action_lock.locked():
                    continue
                evicted_state = self.sessions.get(owner_key)
                if evicted_state is None:
                    continue
                self.sessions.pop(owner_key)
                to_close.append(evicted_state)
        for owner_key in list(self.owner_create_locks.keys()):
            if owner_key not in self.sessions:
                self.owner_create_locks.pop(owner_key, None)
    for state in to_close:
        async with browser_action_lock(state):
            await cancel_active_download_tasks(state, reason="prune")
            await maybe_save_storage_state_for_session(
                config=self.config,
                state=state,
                reason="prune",
                force=True,
            )
            await close_browser_context(
                state,
                "mcp.browser.session_store.prune.close_context",
            )


async def close_owner_session(
    self: BrowserSessionStoreProtocol,
    owner_key: str,
    *,
    persist: bool = True,
) -> None:
    key = owner_key.strip() if isinstance(owner_key, str) else ""
    if not key:
        return
    state: BrowserSessionState | None = None
    async with self.sessions_lock:
        state = self.sessions.get(key)
        if state is not None:
            self.sessions.pop(key)
        self.owner_create_locks.pop(key, None)
    if state is None:
        return
    async with browser_action_lock(state):
        await cancel_active_download_tasks(state, reason="close_owner_session")
        if persist:
            await maybe_save_storage_state_for_session(
                config=self.config,
                state=state,
                reason="close_owner_session",
                force=True,
            )
        async with state.lock:
            await close_browser_context(
                state,
                "mcp.browser.session_store.close_owner_session.close_context",
            )


def _log_noncritical_profile_lock_error(
    logger: LoggerProtocol,
    exception: BaseException,
    *,
    owner_key: str,
) -> None:
    coerced = coerce_to_soai_error(
        exception,
        operation="mcp.browser.session_store.close_context.release_profile_lock",
    )
    log_handled_exception(
        logger,
        coerced,
        message="Failed to release browser profile lock (non-critical).",
        operation=OPERATION,
        details={"owner_key": owner_key},
        level="debug",
    )
