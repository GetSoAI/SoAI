"""SoAI - Calendar MCP tool definitions [backend/mcp/calendar/tool_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.shared.tool_annotations import build_tool_annotation_profiles
from mcp.shared.tool_definitions import build_tool_definition
from mcp.tools.icons import ICON_CALENDAR

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_calendar_tool_definitions",)


def build_calendar_tool_definitions() -> dict[str, JSONDict]:
    read_only_annotations, sync_annotations, destructive_annotations = (
        build_tool_annotation_profiles()
    )
    return {
        "calendar_accounts_list": _build_definition(
            title="Calendar Accounts List",
            description="List configured calendar accounts for the authenticated user.",
            properties={},
            required=(),
            annotations=read_only_annotations,
        ),
        "calendar_calendars_list": _build_definition(
            title="Calendar Calendars List",
            description="List cached calendars for one calendar account.",
            properties={
                "account_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
                "cursor": {"type": "string"},
                "order_by": {"type": "string", "enum": ["name"]},
                "order_direction": {"type": "string", "enum": ["asc", "desc"]},
            },
            required=("account_id",),
            annotations=read_only_annotations,
        ),
        "calendar_account_sync": _build_definition(
            title="Calendar Account Sync",
            description="Run an explicit remote discovery and cache sync for one calendar account.",
            properties={"account_id": {"type": "string"}},
            required=("account_id",),
            annotations=sync_annotations,
        ),
        "calendar_window_sync": _build_definition(
            title="Calendar Window Sync",
            description="Run an explicit remote sync for one calendar window.",
            properties={
                "calendar_id": {"type": "string"},
                "window_start_ms": {"type": "integer", "minimum": 0},
                "window_end_ms": {"type": "integer", "minimum": 0},
            },
            required=("calendar_id", "window_start_ms", "window_end_ms"),
            annotations=sync_annotations,
        ),
        "calendar_events_list": _build_definition(
            title="Calendar Events List",
            description="List cached calendar events for one window.",
            properties={
                "calendar_id": {"type": "string"},
                "window_start_ms": {"type": "integer", "minimum": 0},
                "window_end_ms": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1},
                "cursor": {"type": "string"},
                "order_by": {"type": "string", "enum": ["start_at_ms", "updated_at_ms", "summary"]},
                "order_direction": {"type": "string", "enum": ["asc", "desc"]},
                "query": {"type": "string"},
                "attendee": {"type": "string"},
                "organizer": {"type": "string"},
            },
            required=("calendar_id",),
            annotations=read_only_annotations,
        ),
        "calendar_event_read": _build_definition(
            title="Calendar Event Read",
            description="Read one cached calendar event.",
            properties={
                "event_id": {"type": "string"},
                "max_chars": {"type": "integer", "minimum": 1, "default": 50000},
                "offset_chars": {"type": "integer", "minimum": 0, "default": 0},
            },
            required=("event_id",),
            annotations=read_only_annotations,
        ),
        "calendar_event_update": _build_definition(
            title="Calendar Event Update",
            description="Create, update, or delete one calendar event.",
            properties={
                "action": {"type": "string", "enum": ["create", "update", "delete"]},
                "calendar_id": {"type": "string"},
                "event_id": {"type": "string"},
                "event": {"type": "object"},
            },
            required=("action", "calendar_id"),
            annotations=destructive_annotations,
        ),
        "calendar_invite_respond": _build_definition(
            title="Calendar Invite Respond",
            description="Respond to one calendar invitation.",
            properties={
                "event_id": {"type": "string"},
                "action": {"type": "string", "enum": ["accept", "tentative", "decline"]},
                "comment": {"type": "string"},
            },
            required=("event_id", "action"),
            annotations=destructive_annotations,
        ),
    }


def _build_definition(
    *,
    title: str,
    description: str,
    properties: dict[str, JSONValue],
    required: tuple[str, ...],
    annotations: dict[str, bool],
) -> JSONDict:
    return build_tool_definition(
        title=title,
        description=description,
        icon_src=ICON_CALENDAR,
        properties=properties,
        required=required,
        annotations=annotations,
    )
