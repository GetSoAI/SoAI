"""SoAI - MCP utility tool definition: random_generate [backend/mcp/tools/utility_tool_definitions/random_generate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_DICE

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_random_generate_tool_definitions",)


def build_random_generate_tool_definitions() -> dict[str, JSONDict]:
    return {
        "random_generate": {
            "title": "Random Generator",
            "description": "Generate random numbers, UUIDs, strings, or make random selections",
            "icons": [build_tool_icon_entry(ICON_DICE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Type of random value: integer, float, uuid, string, choice",
                        "enum": ["integer", "float", "uuid", "string", "choice"],
                    },
                    "min": {
                        "type": "number",
                        "description": "Minimum value for integer/float (default 0)",
                    },
                    "max": {
                        "type": "number",
                        "description": "Maximum value for integer/float (default 100 for integer, 1.0 for float)",
                    },
                    "length": {
                        "type": "integer",
                        "description": "Length for string generation (default 16, max 1024)",
                    },
                    "charset": {
                        "type": "string",
                        "description": "Character set for string: alphanumeric, alpha, numeric, hex, password (default: alphanumeric)",
                    },
                    "choices": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of items for choice operation",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of random values to generate (default 1, max 100)",
                    },
                },
                "required": ["type"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "values": {
                        "type": "array",
                        "description": "Array of generated values",
                    },
                    "type": {"type": "string"},
                    "count": {"type": "integer"},
                },
            },
            "annotations": build_tool_annotation_flags(read_only=True),
        },
    }
