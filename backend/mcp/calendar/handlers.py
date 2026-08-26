"""SoAI - Calendar MCP tool handlers [backend/mcp/calendar/handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from mcp.calendar.resource_uris import CALENDAR_RESOURCE_URI
from mcp.shared.protocol_arguments import (
    optional_non_negative_int_argument,
    optional_positive_int_argument,
    optional_str_argument,
    require_non_negative_int_argument,
    require_str_argument,
)

if TYPE_CHECKING:
    from core.calendar.protocols import CalendarServiceProtocol
    from core.external_accounts.protocols import LinkedAccountQueryProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_calendar_tool_handlers",)


def build_calendar_tool_handlers(
    calendar: CalendarServiceProtocol,
    *,
    account_queries: LinkedAccountQueryProtocol,
    require_authenticated_user_id: Callable[[str], int],
    notify_resource_updated: Callable[[str], Awaitable[None]],
) -> dict[str, Callable[[JSONDict], Awaitable[JSONValue]]]:
    async def calendar_accounts_list(arguments: JSONDict) -> JSONValue:
        _ = arguments
        return await account_queries.list_accounts(
            require_authenticated_user_id("calendar_accounts_list"),
        )

    async def calendar_calendars_list(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_calendars_list")
        return await calendar.list_calendars(
            user_id=user_id,
            account_id=require_str_argument(arguments, "account_id"),
            arguments=arguments,
        )

    async def calendar_account_sync(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_account_sync")
        result = await calendar.sync_account(
            user_id=user_id,
            account_id=require_str_argument(arguments, "account_id"),
        )
        await notify_resource_updated(CALENDAR_RESOURCE_URI)
        return result

    async def calendar_window_sync(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_window_sync")
        result = await calendar.sync_window(
            user_id=user_id,
            calendar_id=require_str_argument(arguments, "calendar_id"),
            window_start_ms=require_non_negative_int_argument(arguments, "window_start_ms"),
            window_end_ms=require_non_negative_int_argument(arguments, "window_end_ms"),
        )
        await notify_resource_updated(CALENDAR_RESOURCE_URI)
        return result

    async def calendar_events_list(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_events_list")
        return await calendar.list_events(
            user_id=user_id,
            calendar_id=require_str_argument(arguments, "calendar_id"),
            arguments=arguments,
        )

    async def calendar_event_read(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_event_read")
        return await calendar.read_event(
            user_id=user_id,
            event_id=require_str_argument(arguments, "event_id"),
            max_chars=optional_positive_int_argument(arguments, "max_chars", 50_000),
            offset_chars=optional_non_negative_int_argument(arguments, "offset_chars", 0),
        )

    async def calendar_event_update(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_event_update")
        result = await calendar.update_event(user_id=user_id, payload=arguments)
        await notify_resource_updated(CALENDAR_RESOURCE_URI)
        return result

    async def calendar_invite_respond(arguments: JSONDict) -> JSONValue:
        user_id = require_authenticated_user_id("calendar_invite_respond")
        result = await calendar.respond_to_invite(
            user_id=user_id,
            event_id=require_str_argument(arguments, "event_id"),
            action=require_str_argument(arguments, "action"),
            comment=optional_str_argument(arguments, "comment"),
        )
        await notify_resource_updated(CALENDAR_RESOURCE_URI)
        return result

    return {
        "calendar_accounts_list": calendar_accounts_list,
        "calendar_calendars_list": calendar_calendars_list,
        "calendar_account_sync": calendar_account_sync,
        "calendar_window_sync": calendar_window_sync,
        "calendar_events_list": calendar_events_list,
        "calendar_event_read": calendar_event_read,
        "calendar_event_update": calendar_event_update,
        "calendar_invite_respond": calendar_invite_respond,
    }
