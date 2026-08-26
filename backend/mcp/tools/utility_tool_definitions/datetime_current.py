"""SoAI - MCP utility tool definition: datetime_current [backend/mcp/tools/utility_tool_definitions/datetime_current.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_CLOCK

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_datetime_current_tool_definitions",)

_DESCRIPTION = (
    "Get current time, convert timezones, and perform date arithmetic. "
    "Supports UTC and IANA timezone conversions, custom datetime formatting, and epoch milliseconds."
)


def build_datetime_current_tool_definitions() -> dict[str, JSONDict]:
    return {
        "datetime_current": {
            "title": "Current Time Date Utilities",
            "description": _DESCRIPTION,
            "icons": [build_tool_icon_entry(ICON_CLOCK)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation: now (get current time), convert (timezone conversion), add_days (add/subtract days), format (custom formatting)",
                        "enum": ["now", "convert", "add_days", "format"],
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name (e.g., 'America/New_York', 'UTC'). Default: UTC",
                    },
                    "source_timezone": {
                        "type": "string",
                        "description": "Source timezone for convert when datetime_str is naive and has no offset",
                    },
                    "target_timezone": {
                        "type": "string",
                        "description": "Target timezone for convert operation",
                    },
                    "datetime_str": {
                        "type": "string",
                        "description": "Datetime string in ISO 8601 format (e.g. '2024-01-15T10:30:00') for convert, add_days, and format operations. Naive inputs are assumed to be in the timezone argument. Use this or datetime_ms, not both.",
                    },
                    "datetime_ms": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Non-negative Unix epoch milliseconds for convert, add_days, and format operations. Use this or datetime_str, not both.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to add for the add_days operation. Use negative values to subtract days.",
                    },
                    "format": {
                        "type": "string",
                        "description": "strftime format string for format operation (default: ISO format)",
                    },
                },
                "required": ["operation"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "datetime_iso": {
                        "type": "string",
                        "description": "ISO format datetime",
                    },
                    "datetime_formatted": {
                        "type": "string",
                        "description": "Formatted datetime string",
                    },
                    "timezone": {"type": "string"},
                    "unix_timestamp": {"type": "number"},
                    "day_of_week": {"type": "string"},
                    "is_dst": {"type": "boolean"},
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
