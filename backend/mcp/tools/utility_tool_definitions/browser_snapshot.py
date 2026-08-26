"""SoAI - MCP utility tool definitions: browser_snapshot [backend/mcp/tools/utility_tool_definitions/browser_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_SNAPSHOT
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_integer_schema,
    nullable_non_empty_string_array_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)
from mcp.tools.utility_tool_definitions.browser_snapshot_schema_primitives import (
    build_snapshot_payload_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_snapshot_tool_definitions",)


def build_browser_snapshot_tool_definitions() -> dict[str, JSONDict]:
    session_params = build_browser_session_param_properties()
    return {
        "browser_snapshot": {
            "title": "Browser Snapshot",
            "description": "Return an accessibility snapshot with stable element refs for the current page. Requires TOOLS.MCP.BROWSER.ENABLED=true. Refs become stale after navigation or tab changes. Supports pagination using start_char and next_start_char.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_SNAPSHOT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    **session_params,
                    "start_char": nullable_integer_schema(minimum=0),
                    "snapshot_roles": nullable_non_empty_string_array_schema(),
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": "string"},
                    **build_snapshot_payload_properties(),
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True, open_world=True),
        },
    }
