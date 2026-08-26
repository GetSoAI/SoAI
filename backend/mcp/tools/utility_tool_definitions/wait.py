"""SoAI - MCP utility tool definition: wait [backend/mcp/tools/utility_tool_definitions/wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_CLOCK
from mcp.tools.wait_policy import MAX_WAIT_SECONDS

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_wait_tool_definitions",)


def build_wait_tool_definitions() -> dict[str, JSONDict]:
    return {
        "wait": {
            "title": "Wait",
            "description": (
                "Wait or sleep for a duration or until a specific date/time, up to 1 week. "
                "Use this to intentionally pause the current agent step when time must pass."
            ),
            "icons": [build_tool_icon_entry(ICON_CLOCK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": f"Seconds to wait (0..{MAX_WAIT_SECONDS}).",
                    },
                    "until": {
                        "type": "string",
                        "description": "ISO 8601 datetime string to wait until (e.g. '2026-03-14T12:00:00Z' or '2026-03-14T12:00:00-04:00').",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name used only when 'until' has no timezone offset (e.g. 'America/New_York'). Default: UTC.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Optional short label explaining why the wait is needed.",
                    },
                },
                "required": [],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "requested_seconds": {"type": "number"},
                    "slept_seconds": {"type": "number"},
                    "target_datetime_utc": {"type": "string"},
                    "started_datetime_utc": {"type": "string"},
                    "completed_datetime_utc": {"type": "string"},
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
