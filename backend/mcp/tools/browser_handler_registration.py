"""SoAI - MCP browser utility handler registration [backend/mcp/tools/browser_handler_registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.types.json import JSONDict, JSONValue
from mcp.tools.browser.tool_actions import (
    tool_browser_click,
    tool_browser_hover,
)
from mcp.tools.browser.tool_autofill_secret import tool_browser_autofill_secret
from mcp.tools.browser.tool_autofill_vault import tool_browser_autofill_vault
from mcp.tools.browser.tool_dialog import tool_browser_dialog
from mcp.tools.browser.tool_downloads import tool_browser_downloads
from mcp.tools.browser.tool_drag import tool_browser_drag
from mcp.tools.browser.tool_eval import tool_browser_eval
from mcp.tools.browser.tool_form_actions import (
    tool_browser_press_key,
    tool_browser_type,
)
from mcp.tools.browser.tool_logs import (
    tool_browser_console,
    tool_browser_network,
)
from mcp.tools.browser.tool_management import (
    tool_browser_close,
    tool_browser_resize,
)
from mcp.tools.browser.tool_navigation import tool_browser_navigate
from mcp.tools.browser.tool_pdf import tool_browser_pdf
from mcp.tools.browser.tool_persistence_reset import tool_browser_persistence_reset
from mcp.tools.browser.tool_profiles import tool_browser_profiles
from mcp.tools.browser.tool_screenshot import tool_browser_screenshot
from mcp.tools.browser.tool_scroll import tool_browser_scroll
from mcp.tools.browser.tool_select_action import tool_browser_select_option
from mcp.tools.browser.tool_snapshot import tool_browser_snapshot
from mcp.tools.browser.tool_status import tool_browser_status
from mcp.tools.browser.tool_tabs import tool_browser_tabs
from mcp.tools.browser.tool_upload_file import tool_browser_upload_file
from mcp.tools.browser.tool_wait import tool_browser_wait_for
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("build_browser_utility_tool_handlers",)


def build_browser_utility_tool_handlers(
    *,
    build_handler: Callable[
        [str, Callable[[JSONDict], Awaitable[JSONValue]]],
        Callable[[JSONDict], Awaitable[JSONValue]],
    ],
    bind_tool: Callable[
        [Callable[[MCPUtilityToolsProtocol, JSONDict], Awaitable[JSONValue]]],
        Callable[[JSONDict], Awaitable[JSONValue]],
    ],
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
    return {
        "browser_navigate": build_handler("browser_navigate", bind_tool(tool_browser_navigate)),
        "browser_snapshot": build_handler("browser_snapshot", bind_tool(tool_browser_snapshot)),
        "browser_click": build_handler("browser_click", bind_tool(tool_browser_click)),
        "browser_autofill_secret": build_handler(
            "browser_autofill_secret",
            bind_tool(tool_browser_autofill_secret),
        ),
        "browser_autofill_vault": build_handler(
            "browser_autofill_vault",
            bind_tool(tool_browser_autofill_vault),
        ),
        "browser_hover": build_handler("browser_hover", bind_tool(tool_browser_hover)),
        "browser_type": build_handler("browser_type", bind_tool(tool_browser_type)),
        "browser_press_key": build_handler("browser_press_key", bind_tool(tool_browser_press_key)),
        "browser_select_option": build_handler(
            "browser_select_option",
            bind_tool(tool_browser_select_option),
        ),
        "browser_wait_for": build_handler("browser_wait_for", bind_tool(tool_browser_wait_for)),
        "browser_scroll": build_handler("browser_scroll", bind_tool(tool_browser_scroll)),
        "browser_drag": build_handler("browser_drag", bind_tool(tool_browser_drag)),
        "browser_upload_file": build_handler(
            "browser_upload_file",
            bind_tool(tool_browser_upload_file),
        ),
        "browser_eval": build_handler("browser_eval", bind_tool(tool_browser_eval)),
        "browser_screenshot": build_handler(
            "browser_screenshot",
            bind_tool(tool_browser_screenshot),
        ),
        "browser_resize": build_handler("browser_resize", bind_tool(tool_browser_resize)),
        "browser_close": build_handler("browser_close", bind_tool(tool_browser_close)),
        "browser_persistence_reset": build_handler(
            "browser_persistence_reset",
            bind_tool(tool_browser_persistence_reset),
        ),
        "browser_tabs": build_handler("browser_tabs", bind_tool(tool_browser_tabs)),
        "browser_console": build_handler("browser_console", bind_tool(tool_browser_console)),
        "browser_network": build_handler("browser_network", bind_tool(tool_browser_network)),
        "browser_profiles": build_handler("browser_profiles", bind_tool(tool_browser_profiles)),
        "browser_status": build_handler("browser_status", bind_tool(tool_browser_status)),
        "browser_pdf": build_handler("browser_pdf", bind_tool(tool_browser_pdf)),
        "browser_dialog": build_handler("browser_dialog", bind_tool(tool_browser_dialog)),
        "browser_downloads": build_handler("browser_downloads", bind_tool(tool_browser_downloads)),
    }
