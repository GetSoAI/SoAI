"""SoAI - Browser autofill references, heuristics, and HTTP authentication [backend/mcp/tools/browser/autofill_flow.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.browser.autofill_support import (
    PasswordFieldNotFoundError,
    fill_fields,
    heuristic_password_locator,
    heuristic_username_locator,
    require_typeable_ref,
)
from mcp.tools.browser.http_auth_autofill import (
    maybe_apply_http_basic_auth_for_autofill,
)
from mcp.tools.browser.timeouts import build_wall_clock_timeout_sec

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from mcp.tools.browser.internal_protocols import BrowserSessionStoreProtocol
    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "BrowserAutofillOutcome",
    "run_browser_autofill_flow",
)


@dataclass(frozen=True, slots=True)
class BrowserAutofillOutcome:
    submitted: bool
    http_auth_applied: bool


async def run_browser_autofill_flow(
    *,
    utility_tools: MCPUtilityToolsProtocol,
    store: BrowserSessionStoreProtocol,
    state: BrowserSessionState,
    page: Page,
    claimed_url: str,
    username_plaintext: str | None,
    password_plaintext: str,
    username_ref: str | None,
    password_ref: str | None,
    submit: bool,
    action_timeout_sec: float,
    reason: str,
) -> BrowserAutofillOutcome:
    resolved_username: Locator | None = None
    resolved_password: Locator | None = None
    using_heuristics = username_ref is None and password_ref is None
    if not using_heuristics:
        if username_ref is not None:
            resolved_username = require_typeable_ref(
                state,
                page,
                username_ref,
                field="username_ref",
            )
        if password_ref is not None:
            resolved_password = require_typeable_ref(
                state,
                page,
                password_ref,
                field="password_ref",
            )
    else:
        try:
            resolved_username = await heuristic_username_locator(page)
            resolved_password = await heuristic_password_locator(page)
        except PasswordFieldNotFoundError:
            handled = await maybe_apply_http_basic_auth_for_autofill(
                utility_tools,
                store,
                state,
                page,
                claimed_url=claimed_url,
                username_plaintext=username_plaintext,
                password_plaintext=password_plaintext,
                submit=submit,
                action_timeout_sec=int(action_timeout_sec),
                reason=reason,
            )
            if handled:
                return BrowserAutofillOutcome(submitted=True, http_auth_applied=True)
            raise

    submitted = False
    async with asyncio.timeout(
        build_wall_clock_timeout_sec(
            timeout_ms=None,
            fallback_timeout_sec=float(action_timeout_sec),
            extra_wait_ms=0,
            buffer_sec=10.0,
        ),
    ):
        submitted = await fill_fields(
            username_locator=resolved_username,
            password_locator=resolved_password,
            username_plaintext=username_plaintext,
            password_plaintext=password_plaintext,
            submit=submit,
        )
    return BrowserAutofillOutcome(submitted=bool(submitted), http_auth_applied=False)
