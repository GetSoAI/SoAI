"""SoAI - MCP read-only utility tool definition envelope [backend/mcp/tools/utility_tool_definitions/readonly_tool_definition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_readonly_tool_definition",)


def build_readonly_tool_definition(
    *,
    title: str,
    description: str,
    icon_src: str,
    output_schema: JSONDict,
) -> JSONDict:
    icons = [build_tool_icon_entry(icon_src)]
    input_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }
    return {
        "title": title,
        "description": description,
        "icons": icons,
        "input_schema": input_schema,
        "output_schema": dict(output_schema),
        "annotations": build_tool_annotation_flags(
            read_only=True,
            destructive=False,
            idempotent=True,
            open_world=False,
        ),
    }
