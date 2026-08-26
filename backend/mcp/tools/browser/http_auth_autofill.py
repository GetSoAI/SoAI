"""SoAI - HTTP Basic Auth handling for browser_autofill_* tools [backend/mcp/tools/browser/http_auth_autofill.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.browser.http_auth_navigation import (
    recreate_context_and_navigate_with_http_credentials,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("maybe_apply_http_basic_auth_for_autofill",)


async def maybe_apply_http_basic_auth_for_autofill(
    utility_tools: MCPUtilityToolsProtocol,
    store: BrowserSessionStoreProtocol,
    state: BrowserSessionState,
    page: Page,
    *,
    claimed_url: str,
    username_plaintext: str | None,
    password_plaintext: str,
    submit: bool,
    action_timeout_sec: int,
    reason: str,
) -> bool:
    if not submit:
        raise MCPToolError(
            -32602,
            f"{reason} cannot apply HTTP Basic Auth when submit=false. Set submit=true to recreate the browser context with HTTP Basic Auth and navigate.",
        )
    username = username_plaintext.strip() if isinstance(username_plaintext, str) else ""
    if not username:
        raise MCPToolError(
            -32602,
            "Username is required for HTTP Basic Auth, but the credential payload is missing it.",
        )
    input_count = await page.locator("input").count()
    form_count = await page.locator("form").count()
    if int(input_count) != 0 or int(form_count) != 0:
        return False
    await recreate_context_and_navigate_with_http_credentials(
        utility_tools,
        store,
        state,
        url=claimed_url,
        username=username,
        password=password_plaintext,
        timeout_ms=int(action_timeout_sec) * 1000,
    )
    return True
