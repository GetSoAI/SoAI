"""SoAI - MCP utility tool definitions: browser_drag [backend/mcp/tools/utility_tool_definitions/browser_drag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_DRAG
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_integer_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_drag_tool_definitions",)


def build_browser_drag_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_DRAG)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_drag": {
            "title": "Browser Drag",
            "description": "Drag an element from one ref (browser_snapshot) or selector to another. When using selectors, they must resolve to exactly one element unless you provide *MatchIndex.",
            "icons": icons,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "element_from": nullable_non_empty_string_schema(
                        description="Optional human-readable source element description.",
                    ),
                    "from_ref": nullable_non_empty_string_schema(
                        description="Source element ref from browser_snapshot.",
                    ),
                    "from_selector": nullable_non_empty_string_schema(
                        description="Source element selector (CSS or Playwright selector engine).",
                    ),
                    "from_match_index": nullable_integer_schema(
                        minimum=0,
                        maximum=100000,
                        description="Optional 0-based index used when from_selector matches multiple elements.",
                    ),
                    "element_to": nullable_non_empty_string_schema(
                        description="Optional human-readable destination element description.",
                    ),
                    "to_ref": nullable_non_empty_string_schema(
                        description="Destination element ref from browser_snapshot.",
                    ),
                    "to_selector": nullable_non_empty_string_schema(
                        description="Destination element selector (CSS or Playwright selector engine).",
                    ),
                    "to_match_index": nullable_integer_schema(
                        minimum=0,
                        maximum=100000,
                        description="Optional 0-based index used when to_selector matches multiple elements.",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "dragged": {"type": "boolean"},
                    "drop_observed": {"type": "boolean"},
                    "fallback_used": {"type": "boolean"},
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=False,
                destructive=False,
                idempotent=False,
                open_world=True,
            ),
        },
    }
