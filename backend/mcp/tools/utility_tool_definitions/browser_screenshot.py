"""SoAI - MCP utility tool definitions: browser_screenshot [backend/mcp/tools/utility_tool_definitions/browser_screenshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_SCREENSHOT
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_boolean_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_screenshot_tool_definitions",)


def build_browser_screenshot_tool_definitions() -> dict[str, JSONDict]:
    session_params = build_browser_session_param_properties()
    return {
        "browser_screenshot": {
            "title": "Browser Screenshot",
            "description": "Take a PNG screenshot of the page or an element by ref.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_SCREENSHOT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "full_page": nullable_boolean_schema(),
                    "element": nullable_non_empty_string_schema(
                        description="Optional human-readable element description.",
                    ),
                    "ref": nullable_non_empty_string_schema(
                        description="Element ref from browser_snapshot.",
                    ),
                    "raw": nullable_boolean_schema(
                        description="If true, return only image_base64 (omit content_type).",
                    ),
                    "filename": nullable_non_empty_string_schema(),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "content_type": {"type": "string"},
                    "image_base64": {"type": "string"},
                },
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
    }
