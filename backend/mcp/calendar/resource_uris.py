"""SoAI - Calendar MCP resource URI builders [backend/mcp/calendar/resource_uris.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from mcp.shared.resource_uris import build_resource_uri

__all__ = (
    "build_calendar_event_resource_uri",
    "build_calendar_window_resource_uri",
)

CALENDAR_RESOURCE_URI = "soai://calendar"


def build_calendar_event_resource_uri(
    event_id: str,
    *,
    max_chars: int = 50_000,
    offset_chars: int = 0,
) -> str:
    return build_resource_uri(
        base_uri=CALENDAR_RESOURCE_URI,
        path=f"/events/{event_id}",
        query_items=(
            ("max_chars", max_chars),
            ("offset_chars", offset_chars),
        ),
    )


def build_calendar_window_resource_uri(
    calendar_id: str,
    *,
    window_start_ms: int,
    window_end_ms: int,
    limit: int,
    order_by: str,
    order_direction: str,
) -> str:
    return build_resource_uri(
        base_uri=CALENDAR_RESOURCE_URI,
        path=f"/calendars/{calendar_id}/window",
        query_items=(
            ("limit", limit),
            ("order_by", order_by),
            ("order_direction", order_direction),
            ("window_end_ms", window_end_ms),
            ("window_start_ms", window_start_ms),
        ),
    )
