"""SoAI - Calendar MCP resource catalog definitions [backend/mcp/calendar/resource_catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_icon_entry
from mcp.calendar.resource_uris import CALENDAR_RESOURCE_URI
from mcp.tools.icons import ICON_CALENDAR

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_calendar_resource_metadata",
    "build_calendar_resource_templates",
)


def build_calendar_resource_templates() -> tuple[JSONDict, ...]:
    return (
        {
            "uriTemplate": "soai://calendar/events/{event_id}?max_chars={max_chars}&offset_chars={offset_chars}",
            "name": "Calendar Event",
            "title": "Calendar Event",
            "description": "Read one cached calendar event with standard chunked-read parameters.",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_CALENDAR, include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.8},
        },
        {
            "uriTemplate": "soai://calendar/calendars/{calendar_id}/window?window_start_ms={window_start_ms}&window_end_ms={window_end_ms}&limit={limit}&order_by={order_by}&order_direction={order_direction}",
            "name": "Calendar Window",
            "title": "Calendar Window",
            "description": "List cached events for one explicit calendar window.",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_CALENDAR, include_size=False)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.7},
        },
    )


def build_calendar_resource_metadata() -> JSONDict:
    return {
        CALENDAR_RESOURCE_URI: {
            "name": "Calendar Accounts",
            "title": "Calendar Accounts",
            "description": "List configured calendar accounts for the authenticated user.",
            "mimeType": "application/json",
            "icons": [build_tool_icon_entry(ICON_CALENDAR)],
            "annotations": {"audience": ["user", "assistant"], "priority": 0.8},
        },
    }
