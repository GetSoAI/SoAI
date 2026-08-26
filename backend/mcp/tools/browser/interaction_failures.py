"""SoAI - Browser interaction failure helpers [backend/mcp/tools/browser/interaction_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.async_api import Error

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from mcp.tools.browser.types import BrowserSessionState

__all__ = (
    "raise_if_dialog_pending",
    "raise_rewritten_interaction_exception",
    "rewrite_interaction_exception",
)


def raise_if_dialog_pending(state: BrowserSessionState, *, tool_name: str) -> None:
    if not state.dialogs:
        return
    dialog = state.dialogs[0]

    raise MCPToolError(
        -32603,
        f"{tool_name} is blocked by a pending {dialog.type} dialog. Call browser_dialog(action='list') and handle it before retrying.",
        {"dialog_id": dialog.dialog_id, "dialog_type": dialog.type},
    )


def rewrite_interaction_exception(
    exception: BaseException,
    *,
    tool_name: str,
) -> MCPToolError | None:
    if isinstance(exception, TimeoutError):
        return MCPToolError(
            -32603,
            f"{tool_name} timed out. If the page changed, call browser_snapshot again. If a popup may be blocking the page, call browser_dialog(action='list').",
        )
    if isinstance(exception, Error):
        lowered = str(exception).lower()
        if "timeout" in lowered and "locator." in lowered:
            original = str(exception).strip() or "Playwright timeout"
            return MCPToolError(
                -32603,
                f"{tool_name} timed out ({original}). If the element is inside an iframe, refresh refs with browser_snapshot and ensure you are targeting the correct frame context. If an overlay intercepts pointer events, use browser_snapshot to identify and dismiss it before retrying.",
            )
        if (
            "locator.wait_for" in lowered
            and "to be visible" in lowered
            and "resolved to hidden <option" in lowered
        ):
            return MCPToolError(
                -32603,
                f"{tool_name} timed out waiting for an <option> to be visible. Native <select> options are hidden until the dropdown is opened. Use state='attached' to wait for existence, or interact with the combobox/select before waiting for visibility.",
            )
        if "dialog" in lowered or "alert" in lowered or "confirm" in lowered or "prompt" in lowered:
            return MCPToolError(
                -32603,
                f"{tool_name} is blocked by a browser dialog. Call browser_dialog(action='list') and handle it before retrying.",
            )
    return None


def raise_rewritten_interaction_exception(exception: BaseException, *, tool_name: str) -> None:
    rewritten = rewrite_interaction_exception(exception, tool_name=tool_name)
    if rewritten is not None:
        raise rewritten from exception
    raise exception
