"""SoAI - HTTP Basic Auth context recreation and navigation [backend/mcp/tools/browser/http_auth_navigation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mcp.tools.browser.http_auth_support import build_playwright_http_credentials
from mcp.tools.browser.navigation_fallback_goto import goto_with_http_fallback
from mcp.tools.browser.navigation_validation import build_navigation_url_candidates
from mcp.tools.browser.security_policy import enforce_browser_navigation_policy
from mcp.tools.browser.session_access import (
    mark_page_load,
    require_browser_enabled,
    require_current_page,
)
from mcp.tools.browser.session_action_lock import require_browser_action_lock_held
from mcp.tools.browser.session_sync import sync_session_state

if TYPE_CHECKING:
    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("recreate_context_and_navigate_with_http_credentials",)


async def recreate_context_and_navigate_with_http_credentials(
    utility_tools: MCPUtilityToolsProtocol,
    store: BrowserSessionStoreProtocol,
    state: BrowserSessionState,
    *,
    url: str,
    username: str,
    password: str,
    timeout_ms: int,
) -> None:
    primary_url, fallback_url = build_navigation_url_candidates(url)
    require_browser_enabled(utility_tools)
    await enforce_browser_navigation_policy(
        utility_tools.config,
        utility_tools.runtime_flags,
        url=primary_url,
        source="MCP browser HTTP auth navigation",
    )
    require_browser_action_lock_held(state=state, source="browser_autofill_* (httpAuth)")
    http_credentials = build_playwright_http_credentials(username, password)
    async with state.lock:
        await sync_session_state(utility_tools.config, state)
        ignore_https_errors = bool(state.ignore_https_errors)
    await store.recreate_context(
        state=state,
        http_credentials=http_credentials,
        ignore_https_errors=ignore_https_errors,
    )
    async with state.lock:
        await sync_session_state(utility_tools.config, state)
        mark_page_load(state)
        page = require_current_page(state)

    async def _enforce_alternative_url_policy(alternative_url: str) -> None:
        await enforce_browser_navigation_policy(
            utility_tools.config,
            utility_tools.runtime_flags,
            url=alternative_url,
            source="MCP browser HTTP auth navigation (http alternative)",
        )

    async with asyncio.timeout((float(timeout_ms) / 1000.0) + 10.0):
        await goto_with_http_fallback(
            page,
            primary_url=primary_url,
            fallback_url=fallback_url,
            wait_until="domcontentloaded",
            timeout=timeout_ms,
            enforce_fallback_policy=_enforce_alternative_url_policy,
        )
