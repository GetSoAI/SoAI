"""SoAI - MCP utility tool definitions: browser mouse actions [backend/mcp/tools/utility_tool_definitions/browser_action_mouse_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_CLICK, ICON_BROWSER_HOVER
from mcp.tools.utility_tool_definitions.browser_action_schema_primitives import (
    BrowserActionSchemaPrimitives,
)
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_boolean_schema,
    nullable_enum_schema,
    nullable_integer_schema,
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_tool_input_schema_primitives import (
    build_inline_snapshot_input_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_action_mouse_tool_definitions",)


def build_browser_action_mouse_tool_definitions(
    primitives: BrowserActionSchemaPrimitives,
) -> dict[str, JSONDict]:
    session_params = primitives.session_params
    element_property = primitives.element_property
    inline_snapshot_output_properties = primitives.inline_snapshot_output_properties
    selector_property: JSONDict = {
        "selector": nullable_non_empty_string_schema(
            description="Element selector (CSS or Playwright selector engine). Alternative to ref.",
        ),
    }
    return {
        "browser_click": {
            "title": "Browser Click",
            "description": "Click an element by ref from browser_snapshot or by selector. Requires TOOLS.MCP.BROWSER.ENABLED=true. If the page navigates or a dialog appears, refresh state with browser_snapshot or browser_dialog before retrying.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_CLICK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **element_property,
                    "ref": nullable_non_empty_string_schema(
                        description="Element ref from browser_snapshot. Alternative to selector.",
                    ),
                    **selector_property,
                    "button": nullable_enum_schema(("left", "right", "middle")),
                    "double_click": nullable_boolean_schema(),
                    "modifiers": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "string",
                            "enum": [
                                "Alt",
                                "Control",
                                "ControlOrMeta",
                                "Meta",
                                "Shift",
                            ],
                            "minLength": 1,
                        },
                    },
                    **build_inline_snapshot_input_properties(),
                    "wait_for_url": nullable_non_empty_string_schema(
                        description=(
                            "Optional SoAI URL pattern (exact URL or glob; * matches across "
                            "the full URL). When set, browser_click waits for page.url to "
                            "match before returning."
                        ),
                    ),
                    "wait_for_url_timeout_ms": nullable_integer_schema(
                        minimum=1,
                        maximum=300000,
                    ),
                    "wait_for_url_wait_until": nullable_enum_schema(
                        ("commit", "domcontentloaded", "load", "networkidle"),
                        description="Only used with wait_for_url. Controls which load event must be reached for the URL match (default: domcontentloaded). Use commit/domcontentloaded for pages that never reach full load.",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "clicked": {"type": "boolean"},
                    **inline_snapshot_output_properties,
                },
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
        "browser_hover": {
            "title": "Browser Hover",
            "description": "Hover an element by ref from browser_snapshot or by selector. Requires TOOLS.MCP.BROWSER.ENABLED=true. If navigation or a major page update occurred, refresh refs with browser_snapshot before retrying.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_HOVER)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **element_property,
                    "ref": nullable_non_empty_string_schema(
                        description="Element ref from browser_snapshot. Alternative to selector.",
                    ),
                    **selector_property,
                    "force": nullable_boolean_schema(
                        description="If true, bypass hit-target checks (useful when overlays intercept pointer events).",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"hovered": {"type": "boolean"}},
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
    }
