"""SoAI - MCP utility tool definition: unit_convert [backend/mcp/tools/utility_tool_definitions/unit_convert.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_CONVERT

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_unit_convert_tool_definitions",)


def build_unit_convert_tool_definitions() -> dict[str, JSONDict]:
    return {
        "unit_convert": {
            "title": "Unit Converter",
            "description": "Convert values between units: temperature, length, weight, data sizes",
            "icons": [build_tool_icon_entry(ICON_CONVERT)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": {"type": "number", "description": "Value to convert"},
                    "from_unit": {
                        "type": "string",
                        "description": (
                            "Source unit (case-insensitive). "
                            "Temperature: c, f, k (or celsius, fahrenheit, kelvin). "
                            "Length: m, km, cm, mm, mi, yd, ft, in. "
                            "Weight: kg, g, mg, lb, oz, t. "
                            "Data: b, kb, mb, gb, tb, pb. "
                            "Full names also accepted (e.g. meters, pounds, gigabytes)."
                        ),
                    },
                    "to_unit": {
                        "type": "string",
                        "description": (
                            "Target unit (case-insensitive). "
                            "Temperature: c, f, k (or celsius, fahrenheit, kelvin). "
                            "Length: m, km, cm, mm, mi, yd, ft, in. "
                            "Weight: kg, g, mg, lb, oz, t. "
                            "Data: b, kb, mb, gb, tb, pb. "
                            "Full names also accepted (e.g. meters, pounds, gigabytes)."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "description": "Unit category (auto-detected if not specified)",
                        "enum": ["temperature", "length", "weight", "data"],
                    },
                },
                "required": ["value", "from_unit", "to_unit"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "number", "description": "Converted value"},
                    "from_value": {"type": "number"},
                    "from_unit": {"type": "string"},
                    "to_unit": {"type": "string"},
                    "category": {"type": "string"},
                    "expression": {
                        "type": "string",
                        "description": "Human-readable conversion",
                    },
                },
            },
            "annotations": build_tool_annotation_flags(
                read_only=True,
                destructive=False,
                idempotent=True,
                open_world=False,
            ),
        },
    }
