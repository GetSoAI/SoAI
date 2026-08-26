"""SoAI - Browser navigation error conversion [backend/mcp/tools/browser/navigation_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from core.errors.public_projection import project_public_exception
from core.runtime.network_policy import is_loopback_host
from mcp.tools.browser.playwright_error_classification import (
    is_loopback_connection_refused_error,
)
from mcp.tools.browser.session_state import (
    mark_browser_session_from_playwright_exception,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from typing import NoReturn

    from core.types.json import JSONDict
    from mcp.tools.browser.types import BrowserSessionState

__all__ = ("raise_navigation_playwright_tool_error",)


def raise_navigation_playwright_tool_error(
    state: BrowserSessionState,
    *,
    exception: BaseException,
    attempted_url: str,
) -> NoReturn:
    mark_browser_session_from_playwright_exception(state, exception=exception)
    message = project_public_exception(exception).message
    data = _build_loopback_connection_refused_data(
        attempted_url=attempted_url,
        exception=exception,
    )
    raise MCPToolError(-32603, message, data=data) from exception


def _build_loopback_connection_refused_data(
    *,
    attempted_url: str,
    exception: BaseException,
) -> JSONDict | None:
    if not is_loopback_connection_refused_error(exception):
        return None
    parsed = urlparse(str(attempted_url or ""))
    if not is_loopback_host(parsed.hostname):
        return None
    return {
        "reason": "loopback_connection_refused",
        "attempted_url": str(attempted_url),
        "hint": (
            "The browser reached loopback but the connection was refused. Confirm the local "
            "server is still alive from the browser runtime; shell PTY cleanup can terminate "
            "shell-backgrounded children unless the server is started as a tracked background "
            "shell session or a separate process session."
        ),
    }
