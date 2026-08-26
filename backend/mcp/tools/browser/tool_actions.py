"""SoAI - Browser tools: interactions [backend/mcp/tools/browser/tool_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from playwright.async_api import Error

from mcp.tools.argument_fields import (
    optional_non_empty_string,
    require_allowed_keys,
)
from mcp.tools.argument_scalars import (
    parse_bool_strict_default,
    parse_optional_int_strict,
)
from mcp.tools.browser.action_input_parsing import parse_button, parse_modifiers
from mcp.tools.browser.action_preflight import prepare_action_page_preflight
from mcp.tools.browser.action_result_payloads import (
    BrowserActionSuccessFlag,
    BrowserInlineSnapshotRequest,
    build_action_success_payload,
)
from mcp.tools.browser.argument_validation import (
    parse_inline_snapshot_request,
    parse_optional_wait_until_strict,
)
from mcp.tools.browser.interaction_failures import (
    raise_if_dialog_pending,
    raise_rewritten_interaction_exception,
)
from mcp.tools.browser.ref_lookup import locator_by_ref, optional_ref
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.timeouts import (
    build_wall_clock_timeout_sec,
    resolve_action_timeout_sec,
    resolve_action_wall_clock_timeout_sec,
)
from mcp.tools.browser.url_wait_patterns import build_url_wait_pattern
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.browser.argument_validation import PageWaitUntil
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "tool_browser_click",
    "tool_browser_hover",
)


def _dialog_count(state: BrowserSessionState) -> int:
    return len(state.dialogs) + state.dialog_queue.qsize()


async def tool_browser_click(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {
                "element",
                "ref",
                "selector",
                "button",
                "double_click",
                "modifiers",
                "include_snapshot",
                "snapshot_roles",
                "wait_for_url",
                "wait_for_url_timeout_ms",
                "wait_for_url_wait_until",
                *BROWSER_SESSION_PARAM_KEYS,
            },
        ),
        tool_name="browser_click",
    )
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    _store, state = await require_existing_session(utility_tools, arguments)
    ref = optional_ref(arguments, key="ref")
    selector = optional_non_empty_string(arguments.get("selector"), key="selector")
    if (ref is None) == (selector is None):
        raise MCPToolError(-32602, "Provide exactly one of ref or selector")
    include_snapshot, snapshot_roles = parse_inline_snapshot_request(arguments)
    wait_for_url = optional_non_empty_string(arguments.get("wait_for_url"), key="wait_for_url")
    wait_for_url_timeout_ms = parse_optional_int_strict(
        arguments.get("wait_for_url_timeout_ms"),
        field_name="wait_for_url_timeout_ms",
        min_value=1,
        max_value=300_000,
    )
    wait_for_url_wait_until_raw = parse_optional_wait_until_strict(
        arguments.get("wait_for_url_wait_until"),
        field_name="wait_for_url_wait_until",
    )
    if wait_for_url_timeout_ms is not None and wait_for_url is None:
        raise MCPToolError(
            -32602,
            "wait_for_url_timeout_ms is only allowed when wait_for_url is provided",
        )
    if wait_for_url_wait_until_raw is not None and wait_for_url is None:
        raise MCPToolError(
            -32602,
            "wait_for_url_wait_until is only allowed when wait_for_url is provided",
        )
    wait_for_url_wait_until: PageWaitUntil | None = wait_for_url_wait_until_raw
    if wait_for_url is not None and wait_for_url_wait_until is None:
        wait_for_url_wait_until = "domcontentloaded"
    wait_for_url_pattern = (
        build_url_wait_pattern(wait_for_url) if wait_for_url is not None else None
    )
    async with browser_action_lock(state):
        async with state.lock:
            preflight = await prepare_action_page_preflight(
                utility_tools,
                state,
            )
            page = preflight.page
            stabilize_ms = preflight.stabilize_ms
            raise_if_dialog_pending(state, tool_name="browser_click")
            if ref is not None:
                locator = locator_by_ref(state, page, ref)
            else:
                if selector is None:
                    raise MCPToolError(-32602, "selector is required when ref is omitted")
                locator = page.locator(selector)
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
            dialog_count_before = _dialog_count(state)
            button = parse_button(arguments.get("button"))
            double_click = parse_bool_strict_default(
                arguments.get("double_click"),
                field_name="double_click",
                default=False,
            )
            modifiers = parse_modifiers(arguments.get("modifiers"))
            wait_timeout_ms: int | None = None
            click_completed = False
        try:
            wall_clock_timeout_sec = resolve_action_wall_clock_timeout_sec(
                utility_tools,
                stabilize_ms=stabilize_ms,
            )
            if wait_for_url is not None:
                wait_timeout_ms = (
                    int(wait_for_url_timeout_ms)
                    if wait_for_url_timeout_ms is not None
                    else int(action_timeout_sec) * 1000
                )
                wall_clock_timeout_sec = max(
                    wall_clock_timeout_sec,
                    build_wall_clock_timeout_sec(
                        timeout_ms=wait_timeout_ms,
                        fallback_timeout_sec=float(action_timeout_sec),
                        extra_wait_ms=stabilize_ms,
                        buffer_sec=10.0,
                    ),
                )
            async with asyncio.timeout(wall_clock_timeout_sec):
                await locator.scroll_into_view_if_needed(timeout=int(action_timeout_sec) * 1000)
                if double_click:
                    await locator.dblclick(button=button, modifiers=modifiers)
                else:
                    await locator.click(button=button, modifiers=modifiers)
                click_completed = True
                if wait_for_url_pattern is not None:
                    await page.wait_for_url(
                        wait_for_url_pattern,
                        timeout=wait_timeout_ms,
                        wait_until=wait_for_url_wait_until,
                    )
                if stabilize_ms:
                    await page.wait_for_timeout(stabilize_ms)
        except (TimeoutError, Error) as exception:
            async with state.lock:
                await sync_session_state(
                    utility_tools.config,
                    state,
                    downloads_dir=preflight.downloads_dir,
                )
                if _dialog_count(state) > dialog_count_before:
                    return await build_action_success_payload(
                        utility_tools,
                        state,
                        preflight=preflight,
                        reason="browser_click",
                        snapshot=BrowserInlineSnapshotRequest(include_snapshot, snapshot_roles),
                        success=BrowserActionSuccessFlag("clicked", True),
                    )
                if click_completed and wait_for_url is not None:
                    current_url = await require_browser_page_output_allowed(
                        utility_tools,
                        page,
                        tool_name="browser_click",
                    )
                    raise MCPToolError(
                        -32603,
                        (
                            "browser_click completed, but the page did not match "
                            f"wait_for_url={wait_for_url!r} before timeout. "
                            f"Current URL: {current_url}"
                        ),
                        data={
                            "wait_for_url": wait_for_url,
                            "current_url": current_url,
                            "timeout_ms": wait_timeout_ms,
                            "wait_until": wait_for_url_wait_until,
                        },
                    ) from exception
            raise_rewritten_interaction_exception(exception, tool_name="browser_click")
        async with state.lock:
            return await build_action_success_payload(
                utility_tools,
                state,
                preflight=preflight,
                reason="browser_click",
                snapshot=BrowserInlineSnapshotRequest(include_snapshot, snapshot_roles),
                success=BrowserActionSuccessFlag("clicked", True),
            )


async def tool_browser_hover(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset(
            {"element", "ref", "selector", "force", *BROWSER_SESSION_PARAM_KEYS},
        ),
        tool_name="browser_hover",
    )
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    _store, state = await require_existing_session(utility_tools, arguments)
    ref = optional_ref(arguments, key="ref")
    selector = optional_non_empty_string(arguments.get("selector"), key="selector")
    if (ref is None) == (selector is None):
        raise MCPToolError(-32602, "Provide exactly one of ref or selector")
    force = parse_bool_strict_default(arguments.get("force"), field_name="force", default=False)
    async with browser_action_lock(state):
        async with state.lock:
            preflight = await prepare_action_page_preflight(utility_tools, state)
            page = preflight.page
            raise_if_dialog_pending(state, tool_name="browser_hover")
            if ref is not None:
                locator = locator_by_ref(state, page, ref)
            else:
                if selector is None:
                    raise MCPToolError(-32602, "selector is required when ref is omitted")
                locator = page.locator(selector)
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
        try:
            async with asyncio.timeout(
                build_wall_clock_timeout_sec(
                    timeout_ms=None,
                    fallback_timeout_sec=float(action_timeout_sec),
                    extra_wait_ms=0,
                    buffer_sec=10.0,
                ),
            ):
                await locator.scroll_into_view_if_needed(timeout=int(action_timeout_sec) * 1000)
                await locator.hover(force=bool(force))
        except (TimeoutError, Error) as exception:
            raise_rewritten_interaction_exception(exception, tool_name="browser_hover")
        async with state.lock:
            await sync_session_state(
                utility_tools.config,
                state,
                downloads_dir=preflight.downloads_dir,
            )
            page_after_action = require_current_page(state)
            await require_browser_page_output_allowed(
                utility_tools,
                page_after_action,
                tool_name="browser_hover",
            )
        return {"hovered": True}
