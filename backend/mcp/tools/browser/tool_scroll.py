"""SoAI - Browser tool: browser_scroll [backend/mcp/tools/browser/tool_scroll.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict
from core.validation.integers import is_strict_int
from mcp.tools.argument_fields import optional_non_empty_string, require_allowed_keys
from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.browser.ref_lookup import locator_by_ref, optional_ref
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_scroll",)


def _resolve_delay_ms(arguments: JSONDict) -> int:
    parsed = parse_optional_int_strict(
        arguments.get("delay_ms"),
        field_name="delay_ms",
        min_value=0,
        max_value=5000,
    )
    return 0 if parsed is None else parsed


def _resolve_delta_x(arguments: JSONDict) -> int:
    parsed = parse_optional_int_strict(
        arguments.get("delta_x"),
        field_name="delta_x",
        min_value=-20000,
        max_value=20000,
    )
    return 0 if parsed is None else parsed


def _resolve_delta_y(arguments: JSONDict) -> int:
    parsed = parse_optional_int_strict(
        arguments.get("delta_y"),
        field_name="delta_y",
        min_value=-20000,
        max_value=20000,
    )
    return 800 if parsed is None else parsed


async def _read_scroll_position(page: Page) -> tuple[int, int, int, bool]:
    payload = await page.evaluate("""
        () => {
            const element = document.scrollingElement || document.documentElement;
            const scroll_top = Math.max(0, Math.floor(element.scrollTop || 0));
            const scroll_height = Math.max(0, Math.floor(element.scrollHeight || 0));
            const client_height = Math.max(0, Math.floor(element.clientHeight || 0));
            const at_bottom = (scroll_top + client_height) >= Math.max(0, scroll_height - 1);
            return { scroll_top, scroll_height, client_height, at_bottom };
        }
        """)
    payload_dict = coerce_json_dict(payload)
    if payload_dict is None:
        raise MCPToolError(-32603, "Unable to read scroll position (invalid evaluate result).")
    scroll_top = payload_dict.get("scroll_top")
    scroll_height = payload_dict.get("scroll_height")
    client_height = payload_dict.get("client_height")
    at_bottom = payload_dict.get("at_bottom")
    if not is_strict_int(scroll_top):
        raise MCPToolError(-32603, "Unable to read scroll_top from page.")
    if not is_strict_int(scroll_height):
        raise MCPToolError(-32603, "Unable to read scroll_height from page.")
    if not is_strict_int(client_height):
        raise MCPToolError(-32603, "Unable to read client_height from page.")
    if not isinstance(at_bottom, bool):
        raise MCPToolError(-32603, "Unable to read at_bottom from page.")
    return (int(scroll_top), int(scroll_height), int(client_height), bool(at_bottom))


async def tool_browser_scroll(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"element", "ref", "delta_x", "delta_y", "steps", "delay_ms"})
        | BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_scroll",
    )
    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    _ = optional_non_empty_string(arguments.get("element"), key="element")
    ref = optional_ref(arguments)
    async with browser_action_lock(state):
        if ref is not None:
            async with state.lock:
                await sync_session_state(utility_tools.config, state)
                page = require_current_page(state)
                await require_browser_page_output_allowed(
                    utility_tools,
                    page,
                    tool_name="browser_scroll",
                )
                action_timeout_sec = resolve_action_timeout_sec(utility_tools)
                async with asyncio.timeout(float(action_timeout_sec) + 30.0):
                    locator = locator_by_ref(state, page, ref)
                    await locator.scroll_into_view_if_needed()
                    scroll_top, scroll_height, client_height, at_bottom = (
                        await _read_scroll_position(page)
                    )
                await require_browser_page_output_allowed(
                    utility_tools,
                    page,
                    tool_name="browser_scroll",
                )
            return {
                "scrolled": True,
                "total_delta_x": 0,
                "total_delta_y": 0,
                "ref": ref,
                "scroll_top": scroll_top,
                "scroll_height": scroll_height,
                "client_height": client_height,
                "at_bottom": at_bottom,
            }
        steps_parsed = parse_optional_int_strict(
            arguments.get("steps"),
            field_name="steps",
            min_value=1,
            max_value=50,
        )
        steps = 1 if steps_parsed is None else steps_parsed
        delay_ms = _resolve_delay_ms(arguments)
        delta_x = _resolve_delta_x(arguments)
        delta_y = _resolve_delta_y(arguments)
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            page = require_current_page(state)
            await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_scroll",
            )
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
            async with asyncio.timeout(float(action_timeout_sec) + 30.0):
                if delta_x == 0 and delta_y == 0:
                    raise MCPToolError(-32602, "delta_x and delta_y cannot both be 0")
                for _ in range(int(steps)):
                    await page.mouse.wheel(delta_x, delta_y)
                    if delay_ms:
                        await page.wait_for_timeout(delay_ms)
                scroll_top, scroll_height, client_height, at_bottom = await _read_scroll_position(
                    page,
                )
                await require_browser_page_output_allowed(
                    utility_tools,
                    page,
                    tool_name="browser_scroll",
                )
            return {
                "scrolled": True,
                "total_delta_x": int(delta_x) * int(steps),
                "total_delta_y": int(delta_y) * int(steps),
                "scroll_top": scroll_top,
                "scroll_height": scroll_height,
                "client_height": client_height,
                "at_bottom": at_bottom,
            }
