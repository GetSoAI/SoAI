"""SoAI - Browser tools: resize and close [backend/mcp/tools/browser/tool_management.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.argument_scalars import parse_optional_int_strict
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    parse_browser_profile,
    parse_browser_session_scope,
    require_browser_enabled,
    require_current_page,
    require_existing_session,
    resolve_browser_owner_key,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "tool_browser_close",
    "tool_browser_resize",
)


async def tool_browser_resize(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"width", "height", *BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_resize",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    width = parse_optional_int_strict(
        arguments.get("width"),
        field_name="width",
        min_value=1,
        max_value=10000,
    )
    height = parse_optional_int_strict(
        arguments.get("height"),
        field_name="height",
        min_value=1,
        max_value=10000,
    )
    if width is None or height is None:
        raise MCPToolError(-32602, "width and height are required")
    async with browser_action_lock(state), state.lock:
        await sync_session_state(utility_tools.config, state)
        page = require_current_page(state)
        await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_resize",
        )
        timeout_sec = resolve_action_timeout_sec(utility_tools)
        async with asyncio.timeout(float(timeout_sec) + 10.0):
            await page.set_viewport_size({"width": width, "height": height})
    return {"resized": True}


async def tool_browser_close(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({*BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_close",
    )
    require_browser_enabled(utility_tools)
    profile = parse_browser_profile(arguments, config=utility_tools.config)
    session_scope = parse_browser_session_scope(arguments, config=utility_tools.config)
    owner_key = resolve_browser_owner_key(
        utility_tools,
        profile=profile,
        session_scope=session_scope,
    )
    await utility_tools.browser_sessions.close_owner_session(owner_key)
    return {"closed": True}
