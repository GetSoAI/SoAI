"""SoAI - Calendar service query methods [backend/features/calendar/query_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.text.chunked_reads import slice_chunked_text
from core.types.json import JSONDict
from core.validation.strings import coerce_optional_trimmed_str
from features.calendar.calendar_occurrences import expand_events_for_window
from features.calendar.calendar_record_context import load_calendar_row, load_event_row
from features.calendar.calendar_remote_reads import refresh_remote_calendar_event_cache
from features.calendar.event_listing import (
    event_sort_key,
    filter_events,
    resolve_window_bounds,
)
from features.calendar.formatting import (
    format_calendar_entry,
    format_calendar_event,
)
from features.calendar.internal_protocols import CalendarRemoteReadServiceProtocol
from features.external_accounts.listing_support import (
    paginate_json_items,
    resolve_direction,
    resolve_limit,
    resolve_order,
)

__all__ = (
    "list_calendars_method",
    "list_events_method",
    "read_event_method",
)


async def list_calendars_method(
    self: CalendarRemoteReadServiceProtocol,
    *,
    user_id: int,
    account_id: str,
    arguments: JSONDict,
) -> JSONDict:
    account = await self.database_calendar.get_account(user_id=user_id, account_id=account_id)
    if account is None:
        raise ValidationError("Calendar account not found.")
    limit = resolve_limit(
        self.config,
        arguments.get("limit"),
        "INTEGRATIONS.CALENDAR.LIMITS.LIST_DEFAULT",
        "INTEGRATIONS.CALENDAR.LIMITS.LIST_MAX",
    )
    order_by = resolve_order(arguments.get("order_by"), ("name",), "name")
    order_direction = resolve_direction(arguments.get("order_direction"), default_value="asc")
    calendars = await self.database_calendar.list_calendars(user_id=user_id, account_id=account_id)
    formatted = [format_calendar_entry(calendar_row) for calendar_row in calendars]
    formatted.sort(
        key=lambda item: str(item.get(order_by) or "").lower(),
        reverse=(order_direction == "desc"),
    )
    return paginate_json_items(
        supported_sort_fields=("name",),
        order_direction=order_direction,
        order_by=order_by,
        limit=limit,
        cursor=coerce_optional_trimmed_str(arguments.get("cursor")),
        items=formatted,
    )


async def list_events_method(
    self: CalendarRemoteReadServiceProtocol,
    *,
    user_id: int,
    calendar_id: str,
    arguments: JSONDict,
) -> JSONDict:
    await load_calendar_row(
        self.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    limit = resolve_limit(
        self.config,
        arguments.get("limit"),
        "INTEGRATIONS.CALENDAR.LIMITS.LIST_DEFAULT",
        "INTEGRATIONS.CALENDAR.LIMITS.LIST_MAX",
    )
    order_by = resolve_order(
        arguments.get("order_by"),
        ("start_at_ms", "updated_at_ms", "summary"),
        "start_at_ms",
    )
    order_direction = resolve_direction(arguments.get("order_direction"), default_value="asc")
    window_start_ms, window_end_ms = resolve_window_bounds(self.config, arguments)
    events = await self.database_calendar.list_events(user_id=user_id, calendar_id=calendar_id)
    max_expansions_per_event = max(
        1,
        int(self.config.get_int("INTEGRATIONS.CALENDAR.RECURRENCE.MAX_EXPANSIONS_PER_EVENT")),
    )
    expanded_events = expand_events_for_window(
        events=events,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
        max_expansions_per_event=max_expansions_per_event,
    )
    filtered = filter_events(
        expanded_events,
        arguments=arguments,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
    )
    formatted = [format_calendar_event(event_row) for event_row in filtered]
    formatted.sort(
        key=lambda item: event_sort_key(item, order_by),
        reverse=(order_direction == "desc"),
    )
    sync_windows = await self.database_calendar.list_sync_windows(calendar_id=calendar_id)
    coverage = _build_cache_coverage(
        sync_windows=sync_windows,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
    )
    page = paginate_json_items(
        items=formatted,
        cursor=coerce_optional_trimmed_str(arguments.get("cursor")),
        limit=limit,
        order_by=order_by,
        order_direction=order_direction,
        supported_sort_fields=("start_at_ms", "updated_at_ms", "summary"),
    )
    page["cache_coverage"] = coverage
    return page


async def read_event_method(
    self: CalendarRemoteReadServiceProtocol,
    *,
    user_id: int,
    event_id: str,
    max_chars: int,
    offset_chars: int,
) -> JSONDict:
    event_row = await load_event_row(
        self.database_calendar,
        user_id=user_id,
        event_id=event_id,
    )
    warnings: list[str] = []
    raw_ics_value = event_row.get("raw_ics")
    if not isinstance(raw_ics_value, str) or not raw_ics_value:
        refreshed_event, refresh_warnings = await refresh_remote_calendar_event_cache(
            self,
            user_id=user_id,
            event_id=event_id,
        )
        event_row = refreshed_event
        warnings.extend(refresh_warnings)
    raw_ics_value = event_row.get("raw_ics")
    raw_ics = raw_ics_value if isinstance(raw_ics_value, str) else ""
    chunk = slice_chunked_text(
        content=raw_ics,
        max_chars=max(1, max_chars),
        offset_chars=max(offset_chars, 0),
        content_complete=True,
    )
    warnings.extend(chunk.warnings)
    return {
        "event": format_calendar_event(event_row),
        "raw_ics": chunk.content,
        "truncated": chunk.truncated,
        "offset_chars": chunk.offset_chars,
        "next_offset_chars": chunk.next_offset_chars,
        "total_chars": len(raw_ics),
        "warnings": warnings,
    }


def _build_cache_coverage(
    *,
    sync_windows: list[JSONDict],
    window_start_ms: int,
    window_end_ms: int,
) -> JSONDict:
    relevant: list[JSONDict] = []
    for item in sync_windows:
        start_value = item.get("synced_window_start_ms")
        end_value = item.get("synced_window_end_ms")
        if not isinstance(start_value, int) or not isinstance(end_value, int):
            continue
        if start_value <= window_end_ms and end_value >= window_start_ms:
            relevant.append(item)
    if not relevant:
        return {
            "synced_window_start_ms": None,
            "synced_window_end_ms": None,
            "is_window_limited": True,
        }
    synced_start_values = [
        synced_window_start_ms
        for item in relevant
        if (synced_window_start_ms := _read_synced_window_value(item, "synced_window_start_ms"))
        is not None
    ]
    synced_end_values = [
        synced_window_end_ms
        for item in relevant
        if (synced_window_end_ms := _read_synced_window_value(item, "synced_window_end_ms"))
        is not None
    ]
    synced_start_ms = min(synced_start_values)
    synced_end_ms = max(synced_end_values)
    return {
        "synced_window_start_ms": synced_start_ms,
        "synced_window_end_ms": synced_end_ms,
        "is_window_limited": synced_start_ms > window_start_ms or synced_end_ms < window_end_ms,
    }


def _read_synced_window_value(item: JSONDict, key: str) -> int | None:
    value = item.get(key)
    if isinstance(value, int):
        return value
    return None
