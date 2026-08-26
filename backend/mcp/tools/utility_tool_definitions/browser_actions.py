"""SoAI - MCP utility tool definitions: browser actions [backend/mcp/tools/utility_tool_definitions/browser_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.utility_tool_definitions.browser_action_keyboard_tools import (
    build_browser_action_keyboard_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_action_mouse_tools import (
    build_browser_action_mouse_tool_definitions,
)
from mcp.tools.utility_tool_definitions.browser_action_schema_primitives import (
    build_browser_action_schema_primitives,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_browser_actions_tool_definitions",)


def build_browser_actions_tool_definitions() -> dict[str, JSONDict]:
    primitives = build_browser_action_schema_primitives()
    merged: dict[str, JSONDict] = {}
    merged.update(build_browser_action_mouse_tool_definitions(primitives))
    merged.update(build_browser_action_keyboard_tool_definitions(primitives))
    return merged
