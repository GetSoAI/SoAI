"""SoAI - Browser session store shutdown methods [backend/mcp/tools/browser/session_store_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.tools.browser.download_tasks import cancel_active_download_tasks
from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
from mcp.tools.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_state import browser_session_can_use_context
from mcp.tools.browser.session_store_lifecycle import close_browser_context
from mcp.tools.browser.storage_state import maybe_save_storage_state_for_session
from mcp.tools.browser.types import BrowserSessionState

__all__ = ("shutdown",)

LOGGER_NAME = "SoAI.mcp.tools.session_store_shutdown"
OPERATION = "mcp.browser.session_store.shutdown.runtime_shutdown"
OPERATION_SAVE_STORAGE = "mcp.browser.session_store.shutdown.save_storage_state"
OPERATION_CLOSE_CONTEXT = "mcp.browser.session_store.shutdown.close_context"
SESSION_SHUTDOWN_EXCEPTIONS = (
    *PLAYWRIGHT_OPERATION_EXCEPTIONS,
    *HANDLED_RUNTIME_EXCEPTIONS,
)


def _session_shutdown_details(state: BrowserSessionState) -> dict[str, str]:
    return {
        "owner_key": state.owner_key,
        "profile": state.profile,
        "session_scope": state.session_scope,
    }


async def shutdown(self: BrowserSessionStoreProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    async with self.sessions_lock:
        to_close = list(self.sessions.values())
        self.sessions.clear()
        self.owner_create_locks.clear()
    primary_exception: Exception | None = None
    for state in to_close:
        async with browser_action_lock(state):
            await cancel_active_download_tasks(state, reason="shutdown")
            if browser_session_can_use_context(state):
                try:
                    await maybe_save_storage_state_for_session(
                        config=self.config,
                        state=state,
                        reason="shutdown",
                        force=True,
                    )
                except asyncio.CancelledError as exception:
                    raise_cancelled_error(exception)
                except SESSION_SHUTDOWN_EXCEPTIONS as exception:
                    details = _session_shutdown_details(state)
                    if isinstance(exception, PlaywrightDriverConnectionClosedError):
                        log_handled_exception(
                            logger,
                            exception,
                            message="Skipped browser session storage-state persistence during shutdown because the Playwright driver connection was already closed (non-critical).",
                            operation=OPERATION_SAVE_STORAGE,
                            details=details,
                            level="debug",
                        )
                    else:
                        coerced = coerce_to_soai_error(
                            exception,
                            operation=OPERATION_SAVE_STORAGE,
                            details=details,
                        )
                        log_exception(
                            logger,
                            coerced,
                            message="Failed to save browser session storage state during shutdown.",
                            operation=OPERATION_SAVE_STORAGE,
                            details=details,
                        )
                        if primary_exception is None:
                            primary_exception = exception
            elif state.driver_disconnect_reason is not None:
                state.storage_state_last_error = state.driver_disconnect_reason
            try:
                await close_browser_context(
                    state,
                    "mcp.browser.session_store.shutdown.close_context",
                )
            except asyncio.CancelledError as exception:
                raise_cancelled_error(exception)
            except SESSION_SHUTDOWN_EXCEPTIONS as exception:
                details = _session_shutdown_details(state)
                coerced = coerce_to_soai_error(
                    exception,
                    operation=OPERATION_CLOSE_CONTEXT,
                    details=details,
                )
                log_exception(
                    logger,
                    coerced,
                    message="Failed to close browser session context during shutdown.",
                    operation=OPERATION_CLOSE_CONTEXT,
                    details=details,
                )
                if primary_exception is None:
                    primary_exception = exception
    try:
        await self.runtime.shutdown()
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION,
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to shut down Playwright runtime during shutdown (non-critical).",
            operation=OPERATION,
            details={},
            level="debug",
        )
    if primary_exception is not None:
        raise primary_exception
