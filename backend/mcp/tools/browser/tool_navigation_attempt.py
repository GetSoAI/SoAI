"""SoAI - Browser navigation attempt flow [backend/mcp/tools/browser/tool_navigation_attempt.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.cancellation import raise_cancelled_error
from mcp.tools.browser.playwright_error_classification import (
    is_download_starting_error,
    is_interrupted_chrome_internal_navigation_error,
    is_usable_final_navigation_url,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.security_policy import enforce_browser_navigation_policy
from mcp.tools.browser.session_state import (
    browser_session_can_use_context,
    mark_browser_session_from_playwright_exception,
)

__all__ = ("perform_navigation_with_http_fallback",)

if TYPE_CHECKING:
    from playwright.async_api import Page

    from mcp.tools.browser.argument_validation import PageWaitUntil
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol


def _can_recover_interrupted_navigation(
    *,
    exception: BaseException,
    page: Page,
    state: BrowserSessionState,
) -> bool:
    if isinstance(exception, TimeoutError):
        return False
    if not is_interrupted_chrome_internal_navigation_error(exception):
        return False
    if not browser_session_can_use_context(state):
        return False
    return is_usable_final_navigation_url(str(page.url or ""))


async def perform_navigation_with_http_fallback(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
    page: Page,
    primary_url: str,
    fallback_url: str | None,
    wait_until: PageWaitUntil,
    timeout_ms: int | None,
) -> bool:
    download_started = False
    try:
        await page.goto(primary_url, wait_until=wait_until, timeout=timeout_ms)
    except asyncio.CancelledError as exception:
        raise_cancelled_error(exception)
    except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
        if isinstance(exception, TimeoutError):
            raise
        if is_download_starting_error(exception):
            return True
        if _can_recover_interrupted_navigation(exception=exception, page=page, state=state):
            return False
        mark_browser_session_from_playwright_exception(
            state,
            exception=exception,
        )
        if fallback_url is None or not browser_session_can_use_context(state):
            raise
        await enforce_browser_navigation_policy(
            utility_tools.config,
            utility_tools.runtime_flags,
            url=fallback_url,
            source="MCP browser navigation (http alternative)",
        )
        try:
            await page.goto(fallback_url, wait_until=wait_until, timeout=timeout_ms)
        except asyncio.CancelledError as cancellation_exception:
            raise_cancelled_error(cancellation_exception)
        except PLAYWRIGHT_OPERATION_EXCEPTIONS as alternative_error:
            if isinstance(alternative_error, TimeoutError):
                raise
            if is_download_starting_error(alternative_error):
                download_started = True
            elif _can_recover_interrupted_navigation(
                exception=alternative_error,
                page=page,
                state=state,
            ):
                download_started = False
            else:
                mark_browser_session_from_playwright_exception(
                    state,
                    exception=alternative_error,
                )
                raise
    return download_started
