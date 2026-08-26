"""SoAI - MCP utility tool definitions: browser wait/select [backend/mcp/tools/utility_tool_definitions/browser_action_wait_and_select.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_SELECT_OPTION, ICON_BROWSER_WAIT
from mcp.tools.utility_tool_definitions.browser_action_schema_primitives import (
    build_browser_action_schema_primitives,
)
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    non_empty_string_array_schema,
    nullable_enum_schema,
    nullable_non_empty_string_schema,
    nullable_number_schema,
)
from mcp.tools.utility_tool_definitions.browser_tool_input_schema_primitives import (
    build_inline_snapshot_input_properties,
    build_timeout_ms_property,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_action_wait_and_select_tool_definitions",)


def build_browser_action_wait_and_select_tool_definitions() -> dict[str, JSONDict]:
    primitives = build_browser_action_schema_primitives()
    session_params = primitives.session_params
    element_property = primitives.element_property
    ref_property = primitives.ref_property
    inline_snapshot_output_properties = primitives.inline_snapshot_output_properties
    return {
        "browser_select_option": {
            "title": "Browser Select Option",
            "description": "Select options in a native HTML <select> element by ref from browser_snapshot. Requires TOOLS.MCP.BROWSER.ENABLED=true. Refs become stale after navigation or major page changes. Provide the visible option text exactly as shown in browser_snapshot. For custom JavaScript dropdowns, use browser_click on the individual option elements instead.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_SELECT_OPTION)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ref", "values"],
                "properties": {
                    **element_property,
                    **ref_property,
                    "values": non_empty_string_array_schema(
                        description="Visible option text to select, exactly as shown in browser_snapshot.",
                    ),
                    **build_inline_snapshot_input_properties(),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "selected": {"type": "boolean"},
                    **inline_snapshot_output_properties,
                },
            },
            "annotations": build_tool_annotation_flags(open_world=True),
        },
        "browser_wait_for": {
            "title": "Browser Wait For",
            "description": "Wait for time, for text to appear/disappear, for a browser_snapshot ref to reach a specific state, or for a URL pattern to match. Requires TOOLS.MCP.BROWSER.ENABLED=true. If the page changed before the wait starts, refresh refs with browser_snapshot first. Note: native <select> <option> elements are hidden by default, so waiting for option refs defaults to state='attached' unless you explicitly request another state.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_WAIT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "time": nullable_number_schema(minimum=0, maximum=3600),
                    "text": nullable_non_empty_string_schema(),
                    "text_gone": nullable_non_empty_string_schema(),
                    "url_pattern": nullable_non_empty_string_schema(
                        description=(
                            "Wait until page.url matches this SoAI URL pattern "
                            "(exact URL or glob; * matches across the full URL)."
                        ),
                    ),
                    "url_prefix": nullable_non_empty_string_schema(
                        description="Wait until page.url starts with this prefix.",
                    ),
                    "wait_until": nullable_enum_schema(
                        ("commit", "domcontentloaded", "load", "networkidle"),
                        description="Only used with url_pattern/url_prefix. Controls which load event must be reached for the URL match (default: domcontentloaded). Use commit/domcontentloaded for pages that never reach full load.",
                    ),
                    **build_timeout_ms_property(
                        min_ms=1,
                        max_ms=300_000,
                        description="Maximum wait time in milliseconds.",
                    ),
                    "ref": nullable_non_empty_string_schema(
                        description="Element ref from browser_snapshot.",
                    ),
                    "state": nullable_enum_schema(
                        ("visible", "hidden", "attached", "detached"),
                        description="Only used with ref. Default is 'visible' for most refs; option refs default to 'attached' because native <option> elements are hidden until the <select> opens.",
                    ),
                    "reason": nullable_non_empty_string_schema(
                        description="Optional short label explaining why the wait is needed.",
                    ),
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {"waited": {"type": "boolean"}, "url": {"type": "string"}},
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                idempotent=True,
                open_world=True,
            ),
        },
    }
