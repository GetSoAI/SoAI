"""SoAI - Shared MCP tool definition builders [backend/mcp/shared/tool_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_icon_entry

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_tool_definition",)


def build_tool_definition(
    *,
    title: str,
    description: str,
    icon_src: str,
    properties: dict[str, JSONValue],
    required: tuple[str, ...],
    annotations: dict[str, bool],
) -> JSONDict:
    return {
        "title": title,
        "description": description,
        "icons": [build_tool_icon_entry(icon_src)],
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": list(required),
        },
        "output_schema": {"type": "object"},
        "annotations": dict(annotations),
    }
