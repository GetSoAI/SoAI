"""SoAI - MCP utility tool definition: plan_get [backend/mcp/tools/utility_tool_definitions/plan_get.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.icons import ICON_PLAN
from mcp.tools.utility_tool_definitions.readonly_tool_definition import (
    build_readonly_tool_definition,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_plan_get_tool_definitions",)


def build_plan_get_tool_definitions() -> dict[str, JSONDict]:
    return {
        "plan_get": {
            **build_readonly_tool_definition(
                title="Plan Get",
                description="Fetch the canonical long plan (markdown).",
                icon_src=ICON_PLAN,
                output_schema={
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "revision": {"type": "integer"},
                        "title": {"type": ["string", "null"]},
                        "markdown": {"type": ["string", "null"]},
                    },
                },
            ),
        },
    }
