"""SoAI - Browser autofill execution under session and action locks [backend/mcp/tools/browser/autofill_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.web.site_scope import assert_url_allowed
from mcp.tools.browser.autofill_flow import (
    BrowserAutofillOutcome,
    run_browser_autofill_flow,
)
from mcp.tools.browser.autofill_support import require_same_origin
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import require_current_page
from mcp.tools.browser.session_action_lock import browser_action_lock
from mcp.tools.browser.session_sync import sync_session_state
from mcp.tools.browser.storage_state import persist_synced_browser_action_storage_state
from mcp.tools.browser.timeouts import resolve_action_timeout_sec
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.web.site_scope import SiteScope
    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "BrowserAutofillCredentials",
    "execute_browser_autofill_on_current_page",
)


@dataclass(frozen=True, slots=True)
class BrowserAutofillCredentials:
    scope: SiteScope
    username_plaintext: str | None
    password_plaintext: str


async def execute_browser_autofill_on_current_page(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    store: BrowserSessionStoreProtocol,
    state: BrowserSessionState,
    claimed_url: str,
    scope_mismatch_message: str,
    resolve_credentials: Callable[[str], Awaitable[BrowserAutofillCredentials]],
    username_ref: str | None,
    password_ref: str | None,
    submit: bool,
    reason: str,
    pre_action_lock_operation: Callable[[], Awaitable[None]] | None = None,
    post_action_lock_operation: Callable[[], Awaitable[None]] | None = None,
) -> BrowserAutofillOutcome:
    async with browser_action_lock(state):
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            page = require_current_page(state)
            actual_url = await require_browser_page_output_allowed(
                utility_tools,
                page,
                tool_name=reason,
            )
            require_same_origin(claimed_url=claimed_url, actual_url=actual_url)
            credentials = await resolve_credentials(actual_url)
            try:
                assert_url_allowed(actual_url, credentials.scope)
            except ValueError as exception:
                raise MCPToolError(-32602, scope_mismatch_message) from exception
            action_timeout_sec = resolve_action_timeout_sec(utility_tools)
        if pre_action_lock_operation is not None:
            await pre_action_lock_operation()
        outcome = await run_browser_autofill_flow(
            utility_tools=utility_tools,
            store=store,
            state=state,
            page=page,
            claimed_url=claimed_url,
            username_plaintext=credentials.username_plaintext,
            password_plaintext=credentials.password_plaintext,
            username_ref=username_ref,
            password_ref=password_ref,
            submit=submit,
            action_timeout_sec=float(action_timeout_sec),
            reason=reason,
        )
        async with state.lock:
            await sync_session_state(utility_tools.config, state)
            page_after_action = require_current_page(state)
            await require_browser_page_output_allowed(
                utility_tools,
                page_after_action,
                tool_name=reason,
            )
            storage_reason = f"{reason}.http_basic" if outcome.http_auth_applied else reason
            await persist_synced_browser_action_storage_state(
                utility_tools=utility_tools,
                state=state,
                reason=storage_reason,
            )
        if post_action_lock_operation is not None:
            await post_action_lock_operation()
        return outcome
