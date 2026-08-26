"""SoAI - MCP utility tool definitions: browser keyboard actions [backend/mcp/tools/utility_tool_definitions/browser_action_keyboard_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_PRESS_KEY, ICON_BROWSER_TYPE
from mcp.tools.utility_tool_definitions.browser_action_schema_primitives import (
    BrowserActionSchemaPrimitives,
)
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_schema,
    nullable_boolean_schema,
)
from mcp.tools.utility_tool_definitions.browser_tool_input_schema_primitives import (
    build_inline_snapshot_input_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_action_keyboard_tool_definitions",)


def build_browser_action_keyboard_tool_definitions(
    primitives: BrowserActionSchemaPrimitives,
) -> dict[str, JSONDict]:
    session_params = primitives.session_params
    element_property = primitives.element_property
    ref_property = primitives.ref_property
    inline_snapshot_output_properties = primitives.inline_snapshot_output_properties
    return {
        "browser_type": {
            "title": "Browser Type",
            "description": "Fill an input by ref from browser_snapshot. Requires TOOLS.MCP.BROWSER.ENABLED=true. Refs are page-specific; refresh them after navigation or major page updates.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_TYPE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ref", "text"],
                "properties": {
                    **element_property,
                    **ref_property,
                    "text": {"type": "string"},
                    "submit": nullable_boolean_schema(),
                    **build_inline_snapshot_input_properties(),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "typed": {"type": "boolean"},
                    **inline_snapshot_output_properties,
                },
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
        "browser_press_key": {
            "title": "Browser Press Key",
            "description": "Press a key in the active page. Requires TOOLS.MCP.BROWSER.ENABLED=true. If the expected control is missing because the layout changed, use browser_snapshot or browser_resize first.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_PRESS_KEY)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["key"],
                "properties": {
                    "key": non_empty_string_schema(),
                    **build_inline_snapshot_input_properties(),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "pressed": {"type": "boolean"},
                    **inline_snapshot_output_properties,
                },
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
    }
