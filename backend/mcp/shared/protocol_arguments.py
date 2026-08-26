"""SoAI - Shared MCP protocol argument validation [backend/mcp/shared/protocol_arguments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.argument_numbers import (
    parse_query_int_value,
    parse_required_json_int_value,
)
from core.mcp.argument_validation import require_non_empty_string_value
from core.mcp.validation import get_required_argument
from core.validation.strings import coerce_optional_trimmed_str
from mcp.protocol.types import MCPJSONRPCError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_invalid_params_error",
    "get_required_str",
    "get_required_str_with_missing_message",
    "optional_non_negative_int_argument",
    "optional_positive_int_argument",
    "optional_str_argument",
    "require_non_negative_int_argument",
    "require_str_argument",
    "resolve_non_negative_query_int",
    "resolve_optional_query_str",
    "resolve_positive_query_int",
)


def build_invalid_params_error(message: str) -> MCPJSONRPCError:
    return MCPJSONRPCError(-32602, message)


def require_str_argument(arguments: JSONDict, key: str) -> str:
    return _require_string_argument(
        arguments,
        key,
        missing_message=f"Missing required parameter: {key}",
        type_message=f"{key} must be a non-empty string.",
        empty_message=f"{key} must be a non-empty string.",
    )


def _require_string_argument(
    arguments: JSONDict,
    key: str,
    *,
    missing_message: str,
    type_message: str,
    empty_message: str,
) -> str:
    if key not in arguments:
        raise MCPJSONRPCError(-32602, missing_message)
    return require_non_empty_string_value(
        arguments[key],
        build_error=build_invalid_params_error,
        type_message=type_message,
        empty_message=empty_message,
    )


def get_required_str(arguments: JSONDict, key: str) -> str:
    return _require_string_argument(
        arguments,
        key,
        missing_message=f"{key} must be a non-empty string",
        type_message=f"{key} must be a non-empty string",
        empty_message=f"{key} must be a non-empty string",
    )


def get_required_str_with_missing_message(
    arguments: JSONDict,
    key: str,
    missing_message: str,
) -> str:
    return _require_string_argument(
        arguments,
        key,
        missing_message=missing_message,
        type_message=f"{key} must be a non-empty string",
        empty_message=f"{key} must be a non-empty string",
    )


def optional_str_argument(arguments: JSONDict, key: str) -> str | None:
    return coerce_optional_trimmed_str(arguments.get(key))


def require_non_negative_int_argument(arguments: JSONDict, key: str) -> int:
    value = get_required_argument(
        arguments,
        key,
        missing_message=f"Missing required parameter: {key}",
    )
    return parse_required_json_int_value(
        value,
        build_error=build_invalid_params_error,
        integer_message=f"{key} must be a non-negative integer.",
        range_message=f"{key} must be a non-negative integer.",
        min_value=0,
        max_value=2**63 - 1,
    )


def optional_non_negative_int_argument(arguments: JSONDict, key: str, default_value: int) -> int:
    value = arguments.get(key)
    if value is None:
        return default_value
    return parse_required_json_int_value(
        value,
        build_error=build_invalid_params_error,
        integer_message=f"{key} must be a non-negative integer.",
        range_message=f"{key} must be a non-negative integer.",
        min_value=0,
        max_value=2**63 - 1,
    )


def optional_positive_int_argument(arguments: JSONDict, key: str, default_value: int) -> int:
    value = arguments.get(key)
    if value is None:
        return default_value
    return parse_required_json_int_value(
        value,
        build_error=build_invalid_params_error,
        integer_message=f"{key} must be a positive integer.",
        range_message=f"{key} must be a positive integer.",
        min_value=1,
        max_value=2**63 - 1,
    )


def resolve_non_negative_query_int(
    query: dict[str, list[str]],
    key: str,
    default_value: int,
) -> int:
    return parse_query_int_value(
        query,
        key,
        build_error=build_invalid_params_error,
        integer_message=f"{key} must be an integer.",
        minimum_message=f"{key} must be non-negative.",
        default_value=default_value,
        minimum=0,
    )


def resolve_positive_query_int(
    query: dict[str, list[str]],
    key: str,
    default_value: int,
) -> int:
    return parse_query_int_value(
        query,
        key,
        build_error=build_invalid_params_error,
        integer_message=f"{key} must be an integer.",
        minimum_message=f"{key} must be positive.",
        default_value=default_value,
        minimum=1,
    )


def resolve_optional_query_str(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    normalized = values[0].strip()
    return normalized or None
