"""SoAI - MCP utility tool definitions: browser_tabs [backend/mcp/tools/utility_tool_definitions/browser_tabs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_TABS
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_integer_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_action_input_schema,
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_tabs_tool_definitions",)


def build_browser_tabs_tool_definitions() -> dict[str, JSONDict]:
    session_params = build_browser_session_param_properties()
    return {
        "browser_tabs": {
            "title": "Browser Tabs",
            "description": (
                "List, open, switch, or close tabs in the current browser session. This can "
                "change the active tab and may close an existing tab."
            ),
            "icons": [build_tool_icon_entry(ICON_BROWSER_TABS)],
            "input_schema": build_browser_action_input_schema(
                actions=("list", "new", "switch", "close"),
                session_params=session_params,
                action_description="list/new reject tab_id; switch requires tab_id; close uses tab_id when provided.",
                extra_properties={
                    "tab_id": nullable_integer_schema(
                        minimum=0,
                        description="Tab index for switch/close actions.",
                    ),
                },
            ),
            "output_schema": {
                "type": "object",
                "properties": {
                    "tabs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tab_id": {"type": "integer"},
                                "url": {"type": "string"},
                                "title": {"type": "string"},
                                "has_refs": {"type": "boolean"},
                            },
                        },
                    },
                    "active_tab_id": {"type": "integer"},
                },
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
