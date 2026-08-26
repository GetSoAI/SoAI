"""SoAI - MCP internal utility tool definition: hardware_control [backend/mcp/tools/utility_tool_definitions/hardware_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags
from mcp.tools.utility_tool_definitions.hardware_schema import (
    build_hardware_tool_definition,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_hardware_control_tool_definitions",)


def _numeric_or_auto_property(description: str) -> JSONDict:
    return {
        "type": ["number", "integer", "string"],
        "description": (
            f"{description} Accepts a number, numeric string, or 'auto' when supported."
        ),
    }


def build_hardware_control_tool_definitions() -> dict[str, JSONDict]:
    return {
        "hardware_control": build_hardware_tool_definition(
            title="Hardware Control",
            description=(
                "Inspect GPU control capabilities and apply supported power/fan/clock settings. "
                "Call list first to inspect each GPU's supported controls and capability ranges, "
                "then set only supported controls. Tune one control at a time in small steps, use "
                "'auto' or reset_clocks to undo clock changes, then validate with "
                "hardware_benchmark before choosing final settings. Requires approval."
            ),
            properties={
                "action": {
                    "type": "string",
                    "enum": ["list", "set"],
                    "description": "Use list to inspect supported controls; use set to apply settings.",
                },
                "device_id": {
                    "type": "string",
                    "description": "GPU device_id from hardware_snapshot or hardware_control list.",
                },
                "settings": {
                    "type": "object",
                    "additionalProperties": False,
                    "minProperties": 1,
                    "description": (
                        "One or more GPU settings to apply. Prefer one changed field per call. "
                        "Use only controls marked supported by hardware_control list."
                    ),
                    "properties": {
                        "power_limit": _numeric_or_auto_property("Power limit in watts."),
                        "fan_speed": _numeric_or_auto_property("Fan speed percent."),
                        "core_clock": _numeric_or_auto_property("Core clock in MHz."),
                        "mem_clock": _numeric_or_auto_property("Memory clock in MHz."),
                        "reset_clocks": {
                            "type": "boolean",
                            "description": "Reset core and memory clocks; do not combine with clock values.",
                        },
                    },
                },
            },
            annotations={
                **build_tool_annotation_flags(destructive=True),
                "requiresApprovalHint": True,
            },
        ),
    }
