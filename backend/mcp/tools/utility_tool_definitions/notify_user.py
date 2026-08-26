"""SoAI - MCP utility tool definition: notify_user [backend/mcp/tools/utility_tool_definitions/notify_user.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_annotation_flags, build_tool_icon_entry
from mcp.tools.icons import ICON_BELL

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_notify_user_tool_definitions",)


def build_notify_user_tool_definitions() -> dict[str, JSONDict]:
    link_schema: JSONDict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "link_type": {
                "type": "string",
                "enum": ["url", "conversation", "automation_run"],
                "description": "Link target type.",
            },
            "value": {
                "type": "string",
                "description": (
                    "Link target identifier. For url links, this must be an absolute http:// or "
                    "https:// URL with a host and without embedded credentials."
                ),
            },
        },
        "required": ["link_type", "value"],
    }
    return {
        "notify_user": {
            "title": "Notify User",
            "description": (
                "Create a persisted user notification and enqueue it for realtime delivery. "
                "This does not wait for a user reply."
            ),
            "icons": [build_tool_icon_entry(ICON_BELL)],
            "input_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["info", "success", "warning", "error"],
                        "description": "Notification type.",
                    },
                    "title": {"type": "string", "description": "Notification title."},
                    "message": {"type": "string", "description": "Notification message body."},
                    "source": {
                        "type": ["string", "null"],
                        "description": "Optional source label (e.g. 'automation').",
                    },
                    "link": {
                        "type": ["object", "null"],
                        "description": "Optional notification link target.",
                        "additionalProperties": False,
                        "properties": link_schema["properties"],
                        "required": ["link_type", "value"],
                    },
                },
                "required": ["type", "title", "message"],
            },
            "output_schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "notification": {"type": "object"},
                },
                "required": ["notification"],
            },
            "annotations": build_tool_annotation_flags(),
        },
    }
