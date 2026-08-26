"""SoAI - MCP utility tool definitions: browser_scroll [backend/mcp/tools/utility_tool_definitions/browser_scroll.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_SCROLL
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_integer_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_scroll_tool_definitions",)


def build_browser_scroll_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_SCROLL)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_scroll": {
            "title": "Browser Scroll",
            "description": "Scroll the page (or scroll an element into view by ref).",
            "icons": icons,
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "element": nullable_non_empty_string_schema(
                        description="Optional human-readable element description.",
                    ),
                    "ref": nullable_non_empty_string_schema(
                        description=(
                            "Optional element ref from browser_snapshot. When omitted or null, "
                            "scrolls the page by delta_x/delta_y. When set, scrolls that element "
                            "into view and ignores delta_x/delta_y/steps/delay_ms."
                        ),
                    ),
                    "delta_x": nullable_integer_schema(
                        minimum=-20000,
                        maximum=20000,
                        description="Horizontal page scroll delta per step in pixels.",
                    ),
                    "delta_y": nullable_integer_schema(
                        minimum=-20000,
                        maximum=20000,
                        description="Vertical page scroll delta per step in pixels.",
                    ),
                    "steps": nullable_integer_schema(
                        minimum=1,
                        maximum=50,
                        description="Number of page scroll steps.",
                    ),
                    "delay_ms": nullable_integer_schema(
                        minimum=0,
                        maximum=5000,
                        description="Delay between page scroll steps in milliseconds.",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "scrolled": {"type": "boolean"},
                    "total_delta_x": {"type": "integer"},
                    "total_delta_y": {"type": "integer"},
                    "ref": {"type": "string"},
                    "scroll_top": {"type": "integer"},
                    "scroll_height": {"type": "integer"},
                    "client_height": {"type": "integer"},
                    "at_bottom": {"type": "boolean"},
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
