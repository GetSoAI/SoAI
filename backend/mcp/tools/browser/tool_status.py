"""SoAI - Browser tool: browser_status [backend/mcp/tools/browser/tool_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.browser.page_metadata import safe_page_title
from mcp.tools.browser.page_title_config import (
    resolve_title_retry_attempts,
    resolve_title_retry_delay_ms,
)
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    find_existing_session,
    require_current_page,
)
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page

    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_status",)

OPERATION_MCP_BROWSER_TOOL_STATUS_RESOLVE_CONNECTED = "mcp.browser.tool_status.resolve_connected"


LOGGER_NAME = "SoAI.mcp.tools.tool_status"


def _build_disconnected_status() -> JSONDict:
    return {
        "session_available": False,
        "connected": False,
        "tabs_count": 0,
        "active_tab_id": None,
        "active_url": None,
        "active_title": None,
        "dialogs_pending": 0,
        "console_messages": 0,
        "network_requests": 0,
        "storage_state": {
            "enabled": False,
            "path": None,
            "dirty": False,
            "last_saved_age_sec": None,
            "last_error": None,
        },
        "next_action": "Call browser_navigate first to create a browser session.",
    }


def _resolve_connected(browser: Browser | None) -> bool:
    if browser is None:
        return False
    try:
        return bool(browser.is_connected())
    except RECOVERABLE_EXCEPTIONS as exception:
        operation = "mcp.browser.tool_status.resolve_connected"
        logger = get_logger(LOGGER_NAME)
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to inspect browser connection state (non-critical).",
            operation=OPERATION_MCP_BROWSER_TOOL_STATUS_RESOLVE_CONNECTED,
            details={},
            level="debug",
        )
        return False


async def tool_browser_status(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=BROWSER_SESSION_PARAM_KEYS,
        tool_name="browser_status",
    )
    session = await find_existing_session(utility_tools, arguments=arguments)
    if session is None:
        return _build_disconnected_status()
    _store, state = session
    async with browser_action_lock(state):
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            page: Page = require_current_page(state)
            active_url = await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name="browser_status",
            )
            browser = state.context.browser
            profile = state.profile
            session_scope = state.session_scope
            owner_key = state.owner_key
            persistence_mode = state.persistence_mode
            user_data_dir = state.user_data_dir
            tabs_count = len(state.pages)
            active_tab_id = int(state.active_index)
            dialogs_pending = len(state.dialogs)
            console_messages = len(state.console_messages)
            network_requests = len(state.network_requests)
            now = time.monotonic()
            last_saved_age_sec: float | None = None
            if float(state.storage_state_last_saved_monotonic) > 0.0:
                last_saved_age_sec = max(0.0, now - float(state.storage_state_last_saved_monotonic))
            storage_enabled = bool(
                utility_tools.config.get_bool("TOOLS.MCP.BROWSER.STORAGE_STATE_ENABLED"),
            )
            if state.persistence_mode == "user_data_dir":
                storage_enabled = False
            storage_state_enabled = bool(storage_enabled)
            storage_state_path = state.storage_state_path
            storage_state_dirty = bool(state.storage_state_dirty)
            storage_state_last_error = state.storage_state_last_error
        title = await safe_page_title(
            page,
            timeout_ms=2000,
            retries=resolve_title_retry_attempts(utility_tools.config),
            delay_ms=resolve_title_retry_delay_ms(utility_tools.config),
        )
        return {
            "session_available": True,
            "profile": profile,
            "session_scope": session_scope,
            "owner_key": owner_key,
            "persistence_mode": persistence_mode,
            "user_data_dir": user_data_dir,
            "connected": _resolve_connected(browser),
            "tabs_count": tabs_count,
            "active_tab_id": active_tab_id,
            "active_url": active_url,
            "active_title": title,
            "dialogs_pending": dialogs_pending,
            "console_messages": console_messages,
            "network_requests": network_requests,
            "storage_state": {
                "enabled": storage_state_enabled,
                "path": storage_state_path,
                "dirty": storage_state_dirty,
                "last_saved_age_sec": last_saved_age_sec,
                "last_error": storage_state_last_error,
            },
        }
