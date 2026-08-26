"""SoAI - Browser session action lock context helper [backend/mcp/tools/browser/session_action_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import require_current_page
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
    "finalize_locked_browser_action",
    "locked_browser_action_page",
    "require_browser_action_lock_held",
    "require_synced_browser_page_output",
)


@asynccontextmanager
async def browser_action_lock(state: BrowserSessionState) -> AsyncGenerator[None]:
    async with state.action_lock:
        yield


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
