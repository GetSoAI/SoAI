"""SoAI - Browser Playwright tool error conversion [backend/mcp/tools/browser/playwright_tool_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import NoReturn

from core.errors.public_projection import project_public_exception
from mcp.tools.browser.session_state import (
    mark_browser_session_from_playwright_exception,
)
from mcp.tools.browser.types import BrowserSessionState
from mcp.tools.error import MCPToolError

__all__ = ("raise_playwright_tool_error",)


def raise_playwright_tool_error(
    state: BrowserSessionState,
    *,
    exception: BaseException,
) -> NoReturn:
    mark_browser_session_from_playwright_exception(state, exception=exception)
    raise MCPToolError(-32603, project_public_exception(exception).message) from exception
