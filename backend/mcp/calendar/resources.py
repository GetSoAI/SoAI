"""SoAI - Calendar MCP resource handlers [backend/mcp/calendar/resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from core.mcp.content_envelopes import (
    build_json_resource_content,
    build_resource_contents_result,
)
from mcp.calendar.resource_uris import (
    CALENDAR_RESOURCE_URI,
    build_calendar_event_resource_uri,
    build_calendar_window_resource_uri,
)
from mcp.protocol.types import MCPJSONRPCError
from mcp.shared.protocol_arguments import (
    resolve_non_negative_query_int,
    resolve_optional_query_str,
    resolve_positive_query_int,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.calendar.protocols import CalendarServiceProtocol
    from core.config.protocols import ConfigProtocol
    from core.mcp.protocols_main import MCPServerProtocol
    from core.types.json import JSONDict

__all__ = (
    "make_resource_calendar",
    "read_calendar_resource_uri",
)

_DEFAULT_EVENT_READ_MAX_CHARS = 50_000


def make_resource_calendar(
    server: MCPServerProtocol,
) -> Callable[[], Awaitable[JSONDict]]:
    async def handler() -> JSONDict:
        user_id = server.context.require_authenticated_user_id("Calendar resources")
        payload = await server.calendar_account_queries.list_accounts(user_id)
        return build_json_resource_content(uri=CALENDAR_RESOURCE_URI, payload=payload)

    return handler


async def read_calendar_resource_uri(
    *,
    calendar: CalendarServiceProtocol,
    config: ConfigProtocol,
    uri: str,
    user_id: int,
) -> JSONDict:
    parsed = urlparse(uri)
    if parsed.netloc != "calendar":
        raise MCPJSONRPCError(-32602, f"Unknown calendar resource: {uri}")
    path = parsed.path or ""
    query = parse_qs(parsed.query or "", keep_blank_values=False)
    if path.startswith("/events/"):
        event_id = path.removeprefix("/events/").strip()
        if not event_id:
            raise MCPJSONRPCError(-32602, "Calendar event resource is missing event_id.")
        max_chars = resolve_positive_query_int(query, "max_chars", _DEFAULT_EVENT_READ_MAX_CHARS)
        offset_chars = resolve_non_negative_query_int(query, "offset_chars", 0)
        payload = await calendar.read_event(
            user_id=user_id,
            event_id=event_id,
            max_chars=max_chars,
            offset_chars=offset_chars,
        )
        return build_resource_contents_result(
            build_json_resource_content(
                uri=build_calendar_event_resource_uri(
                    event_id,
                    max_chars=max_chars,
                    offset_chars=offset_chars,
                ),
                payload=payload,
            ),
        )
    if path.startswith("/calendars/") and path.endswith("/window"):
        calendar_id = path.removeprefix("/calendars/").removesuffix("/window").strip("/")
        if not calendar_id:
            raise MCPJSONRPCError(-32602, "Calendar window resource is missing calendar_id.")
        window_start_ms = resolve_non_negative_query_int(
            query,
            "window_start_ms",
            0,
        )
        window_end_ms = resolve_non_negative_query_int(
            query,
            "window_end_ms",
            0,
        )
        limit = resolve_positive_query_int(
            query,
            "limit",
            int(config.get_int("INTEGRATIONS.CALENDAR.LIMITS.LIST_DEFAULT")),
        )
        order_by = resolve_optional_query_str(query, "order_by") or "start_at_ms"
        order_direction = resolve_optional_query_str(query, "order_direction") or "asc"
        payload = await calendar.list_events(
            user_id=user_id,
            calendar_id=calendar_id,
            arguments={
                "window_start_ms": window_start_ms,
                "window_end_ms": window_end_ms,
                "limit": limit,
                "order_by": order_by,
                "order_direction": order_direction,
            },
        )
        return build_resource_contents_result(
            build_json_resource_content(
                uri=build_calendar_window_resource_uri(
                    calendar_id,
                    window_start_ms=window_start_ms,
                    window_end_ms=window_end_ms,
                    limit=limit,
                    order_by=order_by,
                    order_direction=order_direction,
                ),
                payload=payload,
            ),
        )
    raise MCPJSONRPCError(-32602, f"Unknown calendar resource: {uri}")
