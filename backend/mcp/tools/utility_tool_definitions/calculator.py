"""SoAI - MCP utility tool definition: calculator [backend/mcp/tools/utility_tool_definitions/calculator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_CALC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_calculator_tool_definitions",)


def build_calculator_tool_definitions() -> dict[str, JSONDict]:
    return {
        "calculator": {
            "title": "Calculator",
            "description": (
                "Safely evaluate math expressions (no eval). Supports parentheses; + - * / // % ** and '^'; constants "
                "pi, e, tau; functions sqrt, abs, floor, ceil, round, trunc, sin/cos/tan, asin/acos/atan/atan2, "
                "sinh/cosh/tanh, log/ln/log10/log2, exp, hypot, min/max, degrees/radians, pct(p, x), clamp(x, low, high). "
                "Optional 'variables' supplies named numeric values."
            ),
            "icons": [build_tool_icon_entry(ICON_CALC)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression to evaluate. Examples: '2^8', 'sin(pi/2)', 'log(100,10)', 'clamp(x,0,1)'",
                    },
                    "variables": {
                        "type": "object",
                        "description": 'Optional variables for expression evaluation (name -> number). Example: {"x": 1.5, "y": 2}',
                        "additionalProperties": {"type": "number"},
                    },
                },
                "required": ["expression"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "result": {"type": "number", "description": "Calculation result"},
                    "expression": {
                        "type": "string",
                        "description": "Human-readable expression",
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
