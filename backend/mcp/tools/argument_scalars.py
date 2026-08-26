"""SoAI - MCP utility tool scalar argument validation [backend/mcp/tools/argument_scalars.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.argument_numbers import (
    parse_int_in_range_with_default_value,
    parse_optional_clamped_int_value,
    parse_optional_int_strict_value,
    parse_optional_number_strict_value,
    parse_timeout_ms_value,
)
from core.mcp.argument_validation import parse_optional_bool_strict_value
from mcp.tools.error import build_invalid_params_error

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "get_first_present_argument",
    "parse_bool_strict_default",
    "parse_clamped_int",
    "parse_int",
    "parse_optional_bool_strict",
    "parse_optional_int_strict",
    "parse_optional_number_strict",
    "require_non_negative_timeout_ms",
    "require_positive_timeout_ms",
)


def parse_int(value: JSONValue, *, default: int, min_value: int, max_value: int) -> int:
    return parse_int_in_range_with_default_value(
        value,
        default=default,
        fallback=default,
        minimum=min_value,
        maximum=max_value,
    )


def get_first_present_argument(
    arguments: JSONDict,
    *,
    keys: tuple[str, ...],
) -> tuple[JSONValue | None, str | None]:
    for key in keys:
        if key in arguments:
            return (arguments[key], key)
    return (None, None)


def parse_optional_bool_strict(
    value: JSONValue,
    *,
    field_name: str,
    message: str | None = None,
) -> bool | None:
    return parse_optional_bool_strict_value(
        value,
        build_error=build_invalid_params_error,
        message=message or f"{field_name} must be a boolean",
    )


def parse_bool_strict_default(
    value: JSONValue,
    *,
    field_name: str,
    default: bool,
    message: str | None = None,
) -> bool:
    parsed = parse_optional_bool_strict(value, field_name=field_name, message=message)
    if parsed is None:
        return bool(default)
    return bool(parsed)


def parse_optional_int_strict(
    value: JSONValue,
    *,
    field_name: str,
    min_value: int,
    max_value: int,
    integer_message: str | None = None,
    range_message: str | None = None,
) -> int | None:
    return parse_optional_int_strict_value(
        value,
        build_error=build_invalid_params_error,
        integer_message=integer_message or f"{field_name} must be an integer",
        range_message=range_message or f"{field_name} must be between {min_value} and {max_value}",
        min_value=min_value,
        max_value=max_value,
    )


def parse_optional_number_strict(
    value: JSONValue,
    *,
    field_name: str,
    min_value: float,
    max_value: float,
) -> float | None:
    return parse_optional_number_strict_value(
        value,
        build_error=build_invalid_params_error,
        number_message=f"{field_name} must be a number",
        range_message=f"{field_name} must be between {min_value} and {max_value}",
        min_value=min_value,
        max_value=max_value,
    )


def parse_clamped_int(
    value: JSONValue,
    *,
    field_name: str,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    return parse_optional_clamped_int_value(
        value,
        build_error=build_invalid_params_error,
        number_message=f"{field_name} must be a number, got {type(value).__name__}",
        default=default,
        min_value=min_value,
        max_value=max_value,
    )


def _require_timeout_ms(value: JSONValue | None, *, allow_zero: bool) -> int:
    parsed = parse_timeout_ms_value(
        value,
        field_name="timeout_ms",
        build_error=build_invalid_params_error,
        allow_none=True,
        allow_zero=allow_zero,
    )
    if parsed is None:
        return 60_000
    return int(parsed)


def require_non_negative_timeout_ms(value: JSONValue | None) -> int:
    return _require_timeout_ms(value, allow_zero=True)


def require_positive_timeout_ms(value: JSONValue | None) -> int:
    return _require_timeout_ms(value, allow_zero=False)
