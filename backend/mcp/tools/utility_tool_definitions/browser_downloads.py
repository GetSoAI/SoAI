"""SoAI - MCP utility tool definitions: browser downloads [backend/mcp/tools/utility_tool_definitions/browser_downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_DOWNLOADS
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_input_schema,
    build_browser_session_param_properties,
)
from mcp.tools.utility_tool_definitions.browser_snapshot_schema_primitives import (
    build_downloads_output_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_downloads_tool_definitions",)


def build_browser_downloads_tool_definitions() -> dict[str, JSONDict]:
    icon = [build_tool_icon_entry(ICON_BROWSER_DOWNLOADS)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_downloads": {
            "title": "Browser List Downloads",
            "description": (
                "Return downloads captured for the current browser session, including file path "
                "when available and terminal status such as completed, canceled, or failed. A download "
                "is finished when status='completed' and file_path is present."
            ),
            "icons": icon,
            "input_schema": build_browser_session_input_schema(session_params=session_params),
            "output_schema": {
                "type": "object",
                "properties": {
                    **build_downloads_output_properties(),
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True),
        },
    }
