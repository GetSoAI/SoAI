"""SoAI - MCP utility tool definition: hardware_snapshot [backend/mcp/tools/utility_tool_definitions/hardware_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.system_info_keys import SYSTEM_INFO_COMPONENT_KEYS
from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_HARDWARE

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_hardware_snapshot_tool_definitions",)

_DESCRIPTION = (
    "Return a live hardware snapshot from SoAI (CPU/RAM/GPU temps and usage, plus disk space "
    "for the SoAI installation path). Use this before GPU tuning to identify device_id, "
    "vendor, temperature, utilization, VRAM usage, power, clocks, and system memory pressure."
)


def build_hardware_snapshot_tool_definitions() -> dict[str, JSONDict]:
    return {
        "hardware_snapshot": {
            "title": "Hardware Snapshot",
            "description": _DESCRIPTION,
            "icons": [build_tool_icon_entry(ICON_HARDWARE)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "components": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": list(SYSTEM_INFO_COMPONENT_KEYS),
                        },
                        "minItems": 1,
                        "description": (
                            "Component or components to query "
                            "(default includes uptime, os, cpu, memory, gpu)."
                        ),
                    },
                    "include_processes": {
                        "type": "boolean",
                        "description": "Include per-GPU process list. Admin-only (default: false).",
                    },
                },
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "timestamp_ms": {"type": "integer"},
                    "soai_disk_space": {"type": "object"},
                    "summary": {"type": "object"},
                    "capabilities": {"type": "object"},
                    "uptime": {"type": "object"},
                    "os": {"type": "object"},
                    "cpu": {"type": "object"},
                    "cpus": {"type": "array"},
                    "memory": {"type": "object"},
                    "swap": {"type": "object"},
                    "gpu": {"type": "object"},
                    "motherboard": {"type": "object"},
                    "disk": {"type": "object"},
                    "disk_speed": {"type": "object"},
                    "network": {"type": "object"},
                    "network_speed": {"type": "object"},
                    "components": {"type": "array", "items": {"type": "string"}},
                    "include_processes": {"type": "boolean"},
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
