"""SoAI - MCP wait tool implementation [backend/mcp/tools/wait.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.argument_presence import (
    argument_is_blank_placeholder,
    argument_is_zero_number_placeholder,
    get_effective_optional_argument,
)
from core.timing.formatting import (
    datetime_to_utc_iso,
    parse_iso_datetime_preserve_timezone,
    utc_now,
)
from core.timing.timezones import resolve_zoneinfo_required
from mcp.tools.argument_fields import reject_unexpected_parameters
from mcp.tools.error import MCPToolError
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol
from mcp.tools.wait_policy import MAX_WAIT_SECONDS

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("tool_wait",)

_ALLOWED_KEYS: frozenset[str] = frozenset({"seconds", "until", "timezone", "reason"})


def _parse_until_datetime(until_value: str, timezone_name: str) -> datetime:
    try:
        parsed = parse_iso_datetime_preserve_timezone(until_value)
    except ValidationError as exception:
        raise MCPToolError(-32602, "until must be an ISO 8601 datetime string") from exception
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC)
    if timezone_name:
        try:
            tz = resolve_zoneinfo_required(timezone_name)
        except ValidationError as exception:
            raise MCPToolError(-32602, f"Unknown timezone: {timezone_name}") from exception
        parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(UTC)
    return parsed.replace(tzinfo=UTC).astimezone(UTC)


def _seconds_is_until_placeholder(value: JSONValue) -> bool:
    return argument_is_blank_placeholder(value) or argument_is_zero_number_placeholder(value)


async def tool_wait(_utility_tools: MCPUtilityToolsProtocol, arguments: JSONDict) -> JSONDict:
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)

    seconds_raw = get_effective_optional_argument(arguments, "seconds")
    until_raw = get_effective_optional_argument(arguments, "until")
    if until_raw is not None and "seconds" in arguments:
        if _seconds_is_until_placeholder(arguments["seconds"]):
            seconds_raw = None
    timezone_raw = arguments.get("timezone", "UTC")
    if timezone_raw is None:
        timezone_raw = "UTC"
    if not isinstance(timezone_raw, str):
        raise MCPToolError(-32602, "timezone must be a string when provided")
    timezone_name = timezone_raw.strip() or "UTC"

    has_seconds = seconds_raw is not None
    has_until = until_raw is not None
    if has_seconds and has_until:
        raise MCPToolError(-32602, "Provide only one of: seconds, until")
    if not has_seconds and not has_until:
        raise MCPToolError(-32602, "wait requires one of: seconds, until")

    started = utc_now()
    target = started
    requested_seconds = 0.0
    if has_seconds:
        if isinstance(seconds_raw, bool) or not isinstance(seconds_raw, int | float):
            raise MCPToolError(-32602, "seconds must be a number when provided")
        requested_seconds = float(seconds_raw)
        if requested_seconds < 0.0:
            raise MCPToolError(-32602, "seconds must be >= 0")
        if requested_seconds > float(MAX_WAIT_SECONDS):
            raise MCPToolError(-32602, f"seconds must be <= {MAX_WAIT_SECONDS}")
        try:
            target = started + timedelta(seconds=requested_seconds)
        except OverflowError as exception:
            raise MCPToolError(-32602, "seconds value is too large") from exception
    else:
        if not isinstance(until_raw, str) or not until_raw.strip():
            raise MCPToolError(-32602, "until must be a non-empty string when provided")
        target = _parse_until_datetime(until_raw.strip(), timezone_name=timezone_name)
        requested_seconds = (target - started).total_seconds()
        requested_seconds = max(requested_seconds, 0.0)
        if requested_seconds > float(MAX_WAIT_SECONDS):
            raise MCPToolError(
                -32602,
                f"until is too far in the future; max wait is {MAX_WAIT_SECONDS} seconds (1 week)",
            )

    monotonic_start = time.monotonic()
    if requested_seconds > 0.0:
        await asyncio.sleep(requested_seconds)
    slept_seconds = time.monotonic() - monotonic_start
    completed = utc_now()
    return {
        "requested_seconds": float(requested_seconds),
        "slept_seconds": float(slept_seconds),
        "target_datetime_utc": datetime_to_utc_iso(target),
        "started_datetime_utc": datetime_to_utc_iso(started),
        "completed_datetime_utc": datetime_to_utc_iso(completed),
    }
