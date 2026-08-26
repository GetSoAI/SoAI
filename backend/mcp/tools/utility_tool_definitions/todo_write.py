"""SoAI - MCP utility tool definition: todo_write [backend/mcp/tools/utility_tool_definitions/todo_write.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_PLAN

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_todo_write_tool_definitions",)


def build_todo_write_tool_definitions() -> dict[str, JSONDict]:
    todo_item_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "step": {
                "type": "string",
                "description": "Short imperative description of what this item accomplishes (max 200 chars).",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "Current status: pending (not started), in_progress (actively working), or completed (done).",
            },
        },
        "required": ["step", "status"],
    }
    return {
        "todo_write": {
            "title": "Todo Write",
            "description": (
                "Write the canonical conversation todo checklist. "
                "Each call replaces the entire todo list. Keep at most one item in_progress at a time."
            ),
            "icons": [build_tool_icon_entry(ICON_PLAN)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "explanation": {
                        "type": ["string", "null"],
                        "description": "Optional short explanation of what changed in this todo update.",
                    },
                    "todo": {
                        "type": "array",
                        "description": "The full todo as an ordered array of item objects. Each call replaces the entire todo.",
                        "items": todo_item_schema,
                    },
                },
                "required": ["todo"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "revision": {"type": "integer"},
                    "explanation": {"type": ["string", "null"]},
                    "todo": {"type": "array", "items": todo_item_schema},
                },
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
