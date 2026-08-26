"""SoAI - MCP hardware utility tool schema helpers [backend/mcp/tools/utility_tool_definitions/hardware_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_icon_entry
from mcp.tools.icons import ICON_HARDWARE

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_hardware_tool_definition",)


def build_hardware_tool_definition(
    *,
    title: str,
    description: str,
    properties: JSONDict,
    annotations: JSONDict,
) -> JSONDict:
    return {
        "title": title,
        "description": description,
        "icons": [build_tool_icon_entry(ICON_HARDWARE)],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": ["action"],
        },
        "output_schema": {"type": "object", "additionalProperties": True},
        "annotations": annotations,
    }
