"""SoAI - Browser session action lock context helper [backend/mcp/tools/browser/session_action_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from core.browser.playwright_driver_errors import (
    PlaywrightDriverConnectionClosedError,
    classify_playwright_driver_connection_closed_exception,
)
from core.errors.cancellation import raise_cancelled_error
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SoAIError
from core.logging.trace import get_logger
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import require_current_page
from mcp.tools.browser.session_state import mark_browser_session_driver_disconnected
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.storage_state import persist_synced_browser_action_storage_state
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from playwright.async_api import Page

    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "browser_action_lock",
    "browser_session_driver_is_active",
    "finalize_locked_browser_action",
    "locked_browser_action_page",
    "require_browser_action_lock_held",
    "require_synced_browser_page_output",
)

LOGGER_NAME = "SoAI.mcp.tools.session_action_lock"
OPERATION_SESSION_ACTION = "mcp.browser.session_action"


@asynccontextmanager
async def browser_action_lock(
    state: BrowserSessionState,
    *,
    cleanup: bool = False,
    allow_disconnected: bool = False,
) -> AsyncGenerator[None]:
    async with state.action_lock:
        if cleanup:
            yield
            return
        if not allow_disconnected:
            await _require_active_driver(state)
        try:
            yield
        except asyncio.CancelledError as exception:
            raise_cancelled_error(exception)
        except Exception as exception:
            driver_error = classify_playwright_driver_connection_closed_exception(
                exception,
                operation=OPERATION_SESSION_ACTION,
                details={"owner_key": state.owner_key},
            )
            if driver_error is None or (
                isinstance(exception, MCPToolError | SoAIError)
                and not isinstance(exception, PlaywrightDriverConnectionClosedError)
            ):
                raise
            log_exception(
                get_logger(LOGGER_NAME),
                coerce_to_soai_error(
                    driver_error,
                    operation=OPERATION_SESSION_ACTION,
                ),
                message="Browser session lost its Playwright driver connection.",
                operation=OPERATION_SESSION_ACTION,
                details={"owner_key": state.owner_key},
                level="warning",
            )
            mark_browser_session_driver_disconnected(state, reason=str(driver_error))
            if state.driver_disconnect_handler is not None and state.driver_generation is not None:
                await state.driver_disconnect_handler(state.driver_generation, driver_error)
            if driver_error is exception:
                raise
            raise driver_error from exception
        if not allow_disconnected:
            await _require_active_driver(state)


async def _require_active_driver(state: BrowserSessionState) -> None:
    if await browser_session_driver_is_active(state):
        return
    raise MCPToolError(-32603, "Browser session disconnected. Start a new browser session.")


async def browser_session_driver_is_active(state: BrowserSessionState) -> bool:
    if (
        state.driver_generation is None
        or state.driver_generation_is_active is None
        or await state.driver_generation_is_active(state.driver_generation)
    ):
        return True
    mark_browser_session_driver_disconnected(
        state,
        reason="Playwright driver is no longer active.",
    )
    return False


async def require_synced_browser_page_output(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    *,
    tool_name: str,
) -> Page:
    await sync_session_state(utility_tools.config, state)
    page = require_current_page(state)
    await require_browser_page_output_allowed(
        utility_tools,
        page,
        tool_name=tool_name,
    )
    return page


@asynccontextmanager
async def locked_browser_action_page(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    *,
    tool_name: str,
) -> AsyncGenerator[Page]:
    async with browser_action_lock(state):
        async with state.lock:
            page = await require_synced_browser_page_output(
                utility_tools,
                state,
                tool_name=tool_name,
            )
        yield page


async def finalize_locked_browser_action(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    *,
    tool_name: str,
    persist_reason: str,
) -> None:
    async with state.lock:
        await require_synced_browser_page_output(
            utility_tools,
            state,
            tool_name=tool_name,
        )
        await persist_synced_browser_action_storage_state(
            utility_tools=utility_tools,
            state=state,
            reason=persist_reason,
        )


def require_browser_action_lock_held(*, state: BrowserSessionState, source: str) -> None:
    if not state.action_lock.locked():
        raise MCPToolError(
            -32603,
            f"Internal concurrency contract violation: {source} requires the caller to hold the browser session action_lock.",
        )
