"""SoAI - MCP utility tool definition: plan_write [backend/mcp/tools/utility_tool_definitions/plan_write.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_PLAN

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_plan_write_tool_definitions",)


def build_plan_write_tool_definitions() -> dict[str, JSONDict]:
    return {
        "plan_write": {
            "title": "Plan Write",
            "description": "Write the canonical long plan (markdown).",
            "icons": [build_tool_icon_entry(ICON_PLAN)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {
                        "type": ["string", "null"],
                        "description": "Optional short title (max 120 chars).",
                    },
                    "markdown": {
                        "type": "string",
                        "description": "Long plan markdown (max 50k chars); empty clears the plan.",
                    },
                },
                "required": ["markdown"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "revision": {"type": "integer"},
                    "title": {"type": ["string", "null"]},
                    "markdown": {"type": ["string", "null"]},
                },
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
