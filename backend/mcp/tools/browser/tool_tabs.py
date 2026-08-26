"""SoAI - Browser tool: browser_tabs [backend/mcp/tools/browser/tool_tabs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from mcp.tools.argument_fields import (
    require_allowed_keys,
    require_non_empty_string,
)
from mcp.tools.browser.config_values import (
    BROWSER_MAX_CONCURRENT_PAGES_KEY,
    resolve_browser_max_concurrent_pages,
)
from mcp.tools.browser.page_metadata import safe_page_title
from mcp.tools.browser.page_ref_state import (
    restore_active_page_ref_state,
    transfer_active_page_ref_state,
)
from mcp.tools.browser.page_title_config import (
    resolve_title_retry_attempts,
    resolve_title_retry_delay_ms,
)
from mcp.tools.browser.playwright_operation_exceptions import (
    PLAYWRIGHT_OPERATION_EXCEPTIONS,
)
from mcp.tools.browser.playwright_tool_errors import raise_playwright_tool_error
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    mark_event_stream_page_load,
    require_current_page,
    require_existing_session,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.types import BrowserSessionState
from mcp.tools.error import MCPToolError, get_arg

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_tabs",)


def _resolve_max_tabs(utility_tools: MCPUtilityToolsProtocol) -> int:
    return resolve_browser_max_concurrent_pages(utility_tools.config)


async def _list_tabs(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
) -> JSONDict:
    tabs: list[JSONDict] = []
    retries = resolve_title_retry_attempts(utility_tools.config)
    delay_ms = resolve_title_retry_delay_ms(utility_tools.config)
    for idx, page in enumerate(state.pages):
        output_url = await require_browser_page_output_allowed(
            utility_tools,
            page,
            tool_name="browser_tabs",
        )
        if idx == state.active_index:
            has_refs = bool(state.refs)
        else:
            has_refs = id(page) in state.page_ref_states
        tabs.append(
            {
                "tab_id": idx,
                "url": output_url,
                "title": await safe_page_title(
                    page,
                    timeout_ms=2000,
                    retries=retries,
                    delay_ms=delay_ms,
                ),
                "has_refs": has_refs,
            },
        )
    return {"tabs": tabs, "active_tab_id": state.active_index}


async def tool_browser_tabs(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({"action", "tab_id"}) | BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_tabs",
    )
    _store, state = await require_existing_session(utility_tools, arguments=arguments)
    action = require_non_empty_string(get_arg(arguments, "action"), key="action").lower()
    tab_id_value = arguments.get("tab_id")
    tab_id: int | None = None
    if tab_id_value is not None:
        if not is_strict_int(tab_id_value):
            raise MCPToolError(-32602, "tab_id must be an integer when provided")
        tab_id = int(tab_id_value)

    async with browser_action_lock(state), state.lock:
        await sync_session_state(utility_tools.config, state)
        if action == "list":
            if tab_id is not None:
                raise MCPToolError(-32602, "tab_id is not allowed for action=list")
            return await _list_tabs(utility_tools, state)

        if action == "new":
            if tab_id is not None:
                raise MCPToolError(-32602, "tab_id is not allowed for action=new")
            max_tabs = _resolve_max_tabs(utility_tools)
            if len(state.pages) >= max_tabs:
                raise MCPToolError(
                    -32603,
                    (
                        f"Maximum open tabs reached: {len(state.pages)}/{max_tabs}. "
                        f"Close an existing tab or increase {BROWSER_MAX_CONCURRENT_PAGES_KEY}."
                    ),
                )
            page_before = require_current_page(state)
            new_page = await utility_tools.browser_sessions.create_tab(state)
            await sync_session_state(
                utility_tools.config,
                state,
                desired_active_page=new_page,
            )
            active_page = require_current_page(state)
            try:
                await active_page.bring_to_front()
            except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                raise_playwright_tool_error(state, exception=exception)
            if active_page is not page_before:
                transfer_active_page_ref_state(
                    state,
                    outgoing_page=page_before,
                    incoming_page=active_page,
                    reload_incoming=False,
                )
                mark_event_stream_page_load(state)
            return await _list_tabs(utility_tools, state)

        if action == "switch":
            if tab_id is None:
                raise MCPToolError(-32602, "tab_id is required for action=switch")
            if tab_id < 0 or tab_id >= len(state.pages):
                raise MCPToolError(-32602, f"Invalid tab_id: {tab_id}")
            page_before = require_current_page(state)
            desired_page = state.pages[tab_id]
            await sync_session_state(
                utility_tools.config,
                state,
                desired_active_page=desired_page,
            )
            active_page = require_current_page(state)
            try:
                await active_page.bring_to_front()
            except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                raise_playwright_tool_error(state, exception=exception)
            if active_page is not page_before:
                transfer_active_page_ref_state(
                    state,
                    outgoing_page=page_before,
                    incoming_page=active_page,
                    reload_incoming=False,
                )
                mark_event_stream_page_load(state)
            return await _list_tabs(utility_tools, state)

        if action == "close":
            page_before = require_current_page(state)
            idx = tab_id if tab_id is not None else state.active_index
            if idx < 0 or idx >= len(state.pages):
                raise MCPToolError(-32602, f"Invalid tab_id: {idx}")
            closing_page = state.pages[idx]
            is_closing_active = idx == state.active_index
            desired_page_after_close = page_before
            if is_closing_active:
                if idx + 1 < len(state.pages):
                    desired_page_after_close = state.pages[idx + 1]
                elif idx - 1 >= 0:
                    desired_page_after_close = state.pages[idx - 1]
                else:
                    desired_page_after_close = page_before
            try:
                await closing_page.close()
            except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                raise_playwright_tool_error(state, exception=exception)
            await sync_session_state(
                utility_tools.config,
                state,
                desired_active_page=(
                    None
                    if is_closing_active and len(state.pages) == 1
                    else desired_page_after_close
                ),
            )
            active_page = require_current_page(state)
            try:
                await active_page.bring_to_front()
            except PLAYWRIGHT_OPERATION_EXCEPTIONS as exception:
                raise_playwright_tool_error(state, exception=exception)
            if is_closing_active:
                restore_active_page_ref_state(state, incoming_page=active_page)
                mark_event_stream_page_load(state)
            return await _list_tabs(utility_tools, state)

        _ = require_current_page(state)
        raise MCPToolError(-32602, "Invalid action. Expected: list|new|switch|close")
