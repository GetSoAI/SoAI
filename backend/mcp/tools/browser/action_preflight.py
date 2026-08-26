"""SoAI - Browser action preflight helpers [backend/mcp/tools/browser/action_preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mcp.tools.browser.config_values import resolve_browser_render_stabilize_ms
from mcp.tools.browser.download_storage import sync_download_paths
from mcp.tools.browser.security_policy import require_browser_page_output_allowed
from mcp.tools.browser.session_access import require_current_page

if TYPE_CHECKING:
    from playwright.async_api import Page

    from mcp.tools.browser.types import BrowserSessionState
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "BrowserActionPagePreflight",
    "prepare_action_page_preflight",
)


@dataclass(frozen=True, slots=True)
class BrowserActionPagePreflight:
    downloads_dir: str
    page: Page
    url_before: str
    stabilize_ms: int


async def prepare_action_page_preflight(
    utility_tools: MCPUtilityToolsProtocol,
    state: BrowserSessionState,
) -> BrowserActionPagePreflight:
    download_paths = await sync_download_paths(utility_tools, state)
    page = require_current_page(state)
    url_before = await require_browser_page_output_allowed(
        utility_tools,
        page,
        tool_name="browser_action",
    )
    return BrowserActionPagePreflight(
        downloads_dir=download_paths.downloads_dir,
        page=page,
        url_before=url_before,
        stabilize_ms=resolve_browser_render_stabilize_ms(utility_tools.config),
    )
