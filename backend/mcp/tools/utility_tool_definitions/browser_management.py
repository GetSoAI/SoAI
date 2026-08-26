"""SoAI - MCP utility tool definitions: browser management tools [backend/mcp/tools/utility_tool_definitions/browser_management.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_CLOSE, ICON_BROWSER_RESET, ICON_BROWSER_RESIZE
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_management_tool_definitions",)


def build_browser_management_tool_definitions() -> dict[str, JSONDict]:
    session_params = build_browser_session_param_properties()
    return {
        "browser_resize": {
            "title": "Browser Resize",
            "description": "Resize the browser viewport for the current session.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_RESIZE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["width", "height"],
                "properties": {
                    "width": {"type": "integer"},
                    "height": {"type": "integer"},
                    **session_params,
                },
            },
            "output_schema": {"type": "object", "properties": {"resized": {"type": "boolean"}}},
            "annotations": build_tool_annotation_flags(),
        },
        "browser_close": {
            "title": "Browser Close",
            "description": "Close the current browser session for the caller.",
            "icons": [build_tool_icon_entry(ICON_BROWSER_CLOSE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {**session_params},
            },
            "output_schema": {"type": "object", "properties": {"closed": {"type": "boolean"}}},
            "annotations": build_tool_annotation_flags(idempotent=True),
        },
        "browser_persistence_reset": {
            "title": "Browser Persistence Reset",
            "description": (
                "Delete the configured persistence data for this profile and session_scope. "
                "Automatically resets either its user-data-dir profile or storage_state file. "
                "Destructive recovery action; requires confirm=true."
            ),
            "icons": [build_tool_icon_entry(ICON_BROWSER_RESET)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["confirm"],
                "properties": {
                    "confirm": {"type": "boolean"},
                    **session_params,
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "reset": {"type": "boolean"},
                    "deleted": {"type": "boolean"},
                    "persistence_mode": {
                        "type": "string",
                        "enum": ["storage_state", "user_data_dir"],
                    },
                    "profile": {"type": "string"},
                    "session_scope": {"type": "string"},
                },
                "required": [
                    "reset",
                    "deleted",
                    "persistence_mode",
                    "profile",
                    "session_scope",
                ],
            },
            "annotations": build_tool_annotation_flags(destructive=True, idempotent=True),
        },
    }
