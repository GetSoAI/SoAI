"""SoAI - MCP datetime tool implementation [backend/mcp/tools/datetime_tools.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from core.errors.exceptions import ValidationError
from core.mcp.argument_presence import (
    argument_is_zero_number_placeholder,
    key_is_effectively_provided,
)
from core.timing.formatting import (
    parse_iso_datetime_preserve_timezone,
    timestamp_ms_to_utc_datetime,
    utc_now,
)
from core.timing.timezones import resolve_zoneinfo_required
from core.validation.integers import is_strict_int
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("tool_datetime_current",)


async def tool_datetime_current(
    _utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    operation_value = get_arg(arguments, "operation")
    if not isinstance(operation_value, str):
        raise MCPToolError(
            -32602,
            f"Parameter 'operation' must be a string, got {type(operation_value).__name__}",
        )
    operation = operation_value
    if operation == "now":
        timezone_name_raw = arguments.get("timezone", "UTC")
        if not isinstance(timezone_name_raw, str):
            raise MCPToolError(
                -32602,
                f"Parameter 'timezone' must be a string, got {type(timezone_name_raw).__name__}",
            )
        timezone_name = timezone_name_raw
        target_timezone = _get_timezone(timezone_name)
        current_datetime = utc_now().astimezone(target_timezone)
        return _build_result(current_datetime)
    if operation == "convert":
        source_timezone_raw = arguments.get("source_timezone", "UTC")
        if not isinstance(source_timezone_raw, str):
            raise MCPToolError(
                -32602,
                f"Parameter 'source_timezone' must be a string, got {type(source_timezone_raw).__name__}",
            )
        source_timezone_name = source_timezone_raw
        source_timezone = _get_timezone(source_timezone_name)
        target_timezone_raw = get_arg(arguments, "target_timezone")
        if not isinstance(target_timezone_raw, str):
            raise MCPToolError(
                -32602,
                f"Parameter 'target_timezone' must be a string, got {type(target_timezone_raw).__name__}",
            )
        target_timezone_name = target_timezone_raw
        target_timezone = _get_timezone(target_timezone_name)
        datetime_value = _parse_datetime_input(arguments)
        normalized_datetime = _normalize_datetime_for_timezone(datetime_value, source_timezone)
        converted_datetime = normalized_datetime.astimezone(target_timezone)
        return _build_result(converted_datetime)
    if operation == "add_days":
        datetime_value = _parse_datetime_input(arguments)
        days = get_arg(arguments, "days")
        timezone_name_raw = arguments.get("timezone", "UTC")
        if not isinstance(timezone_name_raw, str):
            raise MCPToolError(
                -32602,
                f"Parameter 'timezone' must be a string, got {type(timezone_name_raw).__name__}",
            )
        timezone_name = timezone_name_raw
        if not isinstance(days, int | float):
            raise MCPToolError(
                -32602,
                f"Parameter 'days' must be a number, got {type(days).__name__}",
            )
        days = int(days)
        target_timezone = _get_timezone(timezone_name)
        parsed_datetime = _normalize_datetime_for_timezone(datetime_value, target_timezone)
        result_datetime = parsed_datetime + timedelta(days=days)
        return _build_result(result_datetime)
    if operation == "format":
        datetime_value = _parse_datetime_input(arguments)
        format_raw = arguments.get("format", "%Y-%m-%d %H:%M:%S %Z")
        if not isinstance(format_raw, str):
            raise MCPToolError(
                -32602,
                f"Parameter 'format' must be a string, got {type(format_raw).__name__}",
            )
        format_str = format_raw
        timezone_name_raw = arguments.get("timezone", "UTC")
        if not isinstance(timezone_name_raw, str):
            raise MCPToolError(
                -32602,
                f"Parameter 'timezone' must be a string, got {type(timezone_name_raw).__name__}",
            )
        timezone_name = timezone_name_raw
        target_timezone = _get_timezone(timezone_name)
        parsed_datetime = _normalize_datetime_for_timezone(datetime_value, target_timezone)
        try:
            formatted = parsed_datetime.strftime(format_str)
        except ValueError as exception:
            raise MCPToolError(-32602, f"Invalid format string: {exception}") from exception
        result = _build_result(parsed_datetime)
        result["datetime_formatted"] = formatted
        return result
    raise MCPToolError(-32602, f"Unknown operation: {operation}")


def _get_timezone(tz_name: str) -> ZoneInfo:
    try:
        return resolve_zoneinfo_required(tz_name)
    except ValidationError as exception:
        raise MCPToolError(-32602, f"Unknown timezone: {tz_name}") from exception


def _parse_datetime_input(arguments: JSONDict) -> datetime:
    has_datetime_str = key_is_effectively_provided(arguments, "datetime_str")
    has_datetime_ms = key_is_effectively_provided(arguments, "datetime_ms")
    if has_datetime_str and has_datetime_ms:
        if argument_is_zero_number_placeholder(arguments.get("datetime_ms")):
            has_datetime_ms = False
        else:
            raise MCPToolError(-32602, "Provide only one of 'datetime_str' or 'datetime_ms'.")
    if not has_datetime_str and not has_datetime_ms:
        raise MCPToolError(-32602, "Missing required parameter: datetime_str or datetime_ms")
    if has_datetime_ms:
        datetime_ms_value = get_arg(arguments, "datetime_ms")
        if not is_strict_int(datetime_ms_value):
            raise MCPToolError(
                -32602,
                f"Parameter 'datetime_ms' must be an integer, got {type(datetime_ms_value).__name__}",
            )
        return timestamp_ms_to_utc_datetime(datetime_ms_value)
    datetime_value = get_arg(arguments, "datetime_str")
    if not isinstance(datetime_value, str):
        raise MCPToolError(
            -32602,
            f"Parameter 'datetime_str' must be a string, got {type(datetime_value).__name__}",
        )
    try:
        parsed_datetime = parse_iso_datetime_preserve_timezone(datetime_value)
    except ValidationError as exception:
        raise MCPToolError(
            -32602,
            f"Invalid datetime format: {datetime_value}. Use ISO format or epoch milliseconds.",
        ) from exception
    return parsed_datetime


def _normalize_datetime_for_timezone(datetime_value: datetime, timezone: ZoneInfo) -> datetime:
    if datetime_value.tzinfo is None:
        return datetime_value.replace(tzinfo=timezone)
    return datetime_value.astimezone(timezone)


def _build_result(datetime_value: datetime) -> JSONDict:
    return {
        "datetime_iso": datetime_value.isoformat(),
        "datetime_formatted": datetime_value.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "timezone": (str(datetime_value.tzinfo) if datetime_value.tzinfo else "naive"),
        "unix_timestamp": datetime_value.timestamp(),
        "day_of_week": datetime_value.strftime("%A"),
        "is_dst": bool(datetime_value.dst()) if datetime_value.tzinfo else False,
    }
