"""SoAI - MCP file search schema primitives [backend/mcp/tools/utility_tool_definitions/file_search_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_file_search_input_schema",)


def build_file_search_input_schema(
    *,
    pattern_description: str,
    properties: JSONDict,
) -> JSONDict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "pattern": {
                "type": "string",
                "description": pattern_description,
            },
            **properties,
        },
        "required": ["pattern"],
    }
