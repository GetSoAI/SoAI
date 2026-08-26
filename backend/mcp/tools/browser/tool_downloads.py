"""SoAI - Browser tool: browser_downloads [backend/mcp/tools/browser/tool_downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.argument_fields import require_allowed_keys
from mcp.tools.browser.download_storage import sync_download_paths
from mcp.tools.browser.download_support import downloads_to_dicts
from mcp.tools.browser.session_access import (
    BROWSER_SESSION_PARAM_KEYS,
    require_existing_session,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_browser_downloads",)


async def tool_browser_downloads(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    require_allowed_keys(
        arguments,
        allowed_keys=frozenset({*BROWSER_SESSION_PARAM_KEYS}),
        tool_name="browser_downloads",
    )
    _store, state = await require_existing_session(utility_tools, arguments)
    async with state.lock:
        download_paths = await sync_download_paths(utility_tools, state)
        return {
            "downloads_dir": download_paths.downloads_dir,
            "downloads": downloads_to_dicts(state.downloads),
        }
