"""SoAI - Browser tools: history navigation [backend/mcp/tools/browser/tool_navigation_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.cancellation import raise_cancelled_error
from mcp.tools.browser.argument_validation import parse_inline_snapshot_request
from mcp.tools.browser.config_values import (
    resolve_browser_default_nav_timeout_sec,
    resolve_browser_render_stabilize_ms,
)
from mcp.tools.browser.navigation_result_assembly import (
    NavigationResultPlan,
    build_captured_navigation_result,
)
from mcp.tools.browser.page_ref_state import (
    capture_active_page_ref_state,
    restore_captured_active_page_ref_state,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.playwright_tool_errors import raise_playwright_tool_error
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    mark_page_load,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.timeouts import build_wall_clock_timeout_sec
from mcp.tools.browser.tool_navigation_runtime import (
    read_navigation_page,
    run_post_navigation,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("execute_browser_history_navigation",)

OPERATION_MCP_BROWSER_HISTORY_CAPTURE_SCREENSHOT = "mcp.browser.history.capture_screenshot"
HISTORY_SCREENSHOT_FAILURE_MESSAGE = "Browser history screenshot capture failed."


async def execute_browser_history_navigation(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
    *,
    navigate_backwards: bool,
) -> JSONDict:
    _store, state = await require_existing_session(utility_tools, arguments)
    async with browser_action_lock(state):
        include_snapshot, snapshot_roles = parse_inline_snapshot_request(arguments)
        async with state.lock:
            downloads_dir, page = await read_navigation_page(utility_tools, state)
            await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_navigate",
            )
            nav_timeout_sec = resolve_browser_default_nav_timeout_sec(utility_tools.config)
            stabilize_ms = resolve_browser_render_stabilize_ms(utility_tools.config)
            captured_ref_state = capture_active_page_ref_state(state)
            captured_console_page_load_index = state.console_page_load_index
            captured_network_page_load_index = state.network_page_load_index
            mark_page_load(state)
        async with asyncio.timeout(
            build_wall_clock_timeout_sec(
                timeout_ms=None,
                fallback_timeout_sec=float(nav_timeout_sec),
                extra_wait_ms=stabilize_ms,
                buffer_sec=10.0,
            ),
        ):
            try:
                if navigate_backwards:
                    response = await page.go_back(wait_until="domcontentloaded")
                else:
                    response = await page.go_forward(wait_until="domcontentloaded")
            except asyncio.CancelledError as exception:
                raise_cancelled_error(exception)
            except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                raise_playwright_tool_error(state, exception=exception)
            if response is None:
                direction = "back" if navigate_backwards else "forward"
                async with state.lock:
                    restore_captured_active_page_ref_state(state, captured_ref_state)
                    state.console_page_load_index = captured_console_page_load_index
                    state.network_page_load_index = captured_network_page_load_index
                return {
                    "navigated": False,
                    "reason": "no_history_entry",
                    "direction": direction,
                }

        history_result_plan = NavigationResultPlan(
            title_timeout_ms=int(nav_timeout_sec) * 1000,
            include_snapshot=include_snapshot,
            snapshot_roles=snapshot_roles,
            screenshot_operation=OPERATION_MCP_BROWSER_HISTORY_CAPTURE_SCREENSHOT,
            screenshot_failure_message=HISTORY_SCREENSHOT_FAILURE_MESSAGE,
            screenshot_skip_reason=None,
            extra_fields={
                "navigated": True,
                "direction": "back" if navigate_backwards else "forward",
            },
        )

        async def build_locked_result(page_after_navigation: Page) -> JSONDict:
            return await build_captured_navigation_result(
                utility_tools,
                state,
                page_after_navigation,
                history_result_plan,
            )

        return await run_post_navigation(
            utility_tools,
            state,
            page,
            on_locked_page=build_locked_result,
            downloads_dir=downloads_dir,
            stabilize_ms=stabilize_ms,
            tool_name="browser_navigate",
        )
