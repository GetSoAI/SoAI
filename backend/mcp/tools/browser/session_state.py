"""SoAI - Browser session connectivity state helpers [backend/mcp/tools/browser/session_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.tools.browser.playwright_driver_errors import (
    is_playwright_driver_connection_closed,
)
from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "browser_session_can_use_context",
    "mark_browser_session_context_closed",
    "mark_browser_session_driver_disconnected",
    "mark_browser_session_from_playwright_exception",
    "reset_browser_session_connectivity",
)


def browser_session_can_use_context(state: BrowserSessionState) -> bool:
    return (not bool(state.context_closed)) and bool(state.driver_connected)


def mark_browser_session_context_closed(state: BrowserSessionState) -> None:
    state.context_closed = True


def mark_browser_session_from_playwright_exception(
    state: BrowserSessionState,
    *,
    exception: BaseException,
) -> None:
    message = str(exception).strip()
    if is_playwright_driver_connection_closed(exception):
        mark_browser_session_driver_disconnected(
            state,
            reason=message,
        )
        return
    lowered = message.lower()
    if "closed" in lowered or "target" in lowered or "crashed" in lowered:
        mark_browser_session_context_closed(state)


def mark_browser_session_driver_disconnected(
    state: BrowserSessionState,
    *,
    reason: str,
) -> None:
    state.context_closed = True
    state.driver_connected = False
    state.driver_disconnect_reason = str(reason or "").strip() or None


def reset_browser_session_connectivity(state: BrowserSessionState) -> None:
    state.context_closed = False
    state.driver_connected = True
    state.driver_disconnect_reason = None
