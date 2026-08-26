"""SoAI - MCP utility tool definitions: browser_dialog [backend/mcp/tools/utility_tool_definitions/browser_dialog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BROWSER_DIALOG
from mcp.tools.utility_tool_definitions.browser_schema_properties import (
    nullable_non_empty_string_schema,
)
from mcp.tools.utility_tool_definitions.browser_session_params import (
    build_browser_action_input_schema,
    build_browser_session_param_properties,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_dialog_tool_definitions",)


def build_browser_dialog_tool_definitions() -> dict[str, JSONDict]:
    icons = [build_tool_icon_entry(ICON_BROWSER_DIALOG)]
    session_params = build_browser_session_param_properties()
    return {
        "browser_dialog": {
            "title": "Browser Dialog",
            "description": (
                "List or handle JavaScript dialogs such as alert, confirm, and prompt for the "
                "current browser session."
            ),
            "icons": icons,
            "input_schema": build_browser_action_input_schema(
                actions=("list", "accept", "dismiss", "prompt"),
                session_params=session_params,
                extra_properties={
                    "dialog_id": nullable_non_empty_string_schema(),
                    "prompt_text": nullable_non_empty_string_schema(),
                },
            ),
            "output_schema": {
                "type": "object",
                "properties": {
                    "dialogs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "dialog_id": {"type": "string"},
                                "type": {"type": "string"},
                                "message": {"type": "string"},
                                "default_value": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "handled": {"type": "boolean"},
                    "action": {"type": "string"},
                    "dialog_id": {"type": "string"},
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
