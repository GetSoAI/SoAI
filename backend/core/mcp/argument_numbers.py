"""SoAI - MCP numeric argument validation primitives [backend/core/mcp/argument_numbers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Callable

from core.types.json import JSONValue
from core.validation.integers import coerce_exact_int_or_none, is_strict_int
from core.validation.numbers import coerce_int_in_range_with_default

__all__ = (
    "parse_int_in_range_with_default_value",
    "parse_integer_like_value",
    "parse_optional_clamped_int_value",
    "parse_optional_int_strict_value",
    "parse_optional_number_strict_value",
    "parse_query_int_value",
    "parse_required_json_int_value",
    "parse_timeout_ms_value",
    "require_scalar_value",
)


def parse_int_in_range_with_default_value(
    value: JSONValue,
    *,
    default: int,
    fallback: int,
    minimum: int,
    maximum: int,
) -> int:
    return coerce_int_in_range_with_default(
        value,
        default=default,
        fallback=fallback,
        minimum=minimum,
        maximum=maximum,
    )


def require_scalar_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    invalid_message: str,
    finite_message: str,
) -> str | int | float:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise build_error(invalid_message)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise build_error(finite_message)
        return value
    return value


def parse_optional_int_strict_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    integer_message: str,
    range_message: str,
    min_value: int,
    max_value: int,
) -> int | None:
    if value is None:
        return None
    parsed = coerce_exact_int_or_none(value)
    if parsed is None:
        raise build_error(integer_message)
    if parsed < min_value or parsed > max_value:
        raise build_error(range_message)
    return parsed


def parse_required_json_int_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    integer_message: str,
    range_message: str,
    min_value: int,
    max_value: int,
) -> int:
    if not is_strict_int(value):
        raise build_error(integer_message)
    if value < min_value or value > max_value:
        raise build_error(range_message)
    return value


def parse_timeout_ms_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    field_name: str,
    allow_none: bool,
    allow_zero: bool,
    minimum: int | None = None,
    maximum: int | None = None,
    range_message: str | None = None,
) -> int | None:
    if value is None:
        if allow_none:
            return None
        raise build_error(f"{field_name} must be an integer when provided")
    null_label = " or null" if allow_none else ""
    if not is_strict_int(value):
        raise build_error(f"{field_name} must be an integer{null_label} when provided")
    parsed = int(value)
    if allow_zero:
        if parsed < 0:
            raise build_error(f"{field_name} must be a non-negative integer when provided")
    elif parsed <= 0:
        raise build_error(f"{field_name} must be a positive integer when provided")
    if minimum is not None and parsed < minimum:
        raise build_error(range_message or f"{field_name} must be >= {minimum}")
    if maximum is not None and parsed > maximum:
        raise build_error(range_message or f"{field_name} must be <= {maximum}")
    return int(parsed)


def parse_integer_like_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    integer_message: str,
) -> int:
    parsed = coerce_exact_int_or_none(value)
    if parsed is None:
        raise build_error(integer_message)
    return parsed


def parse_query_int_value(
    query: dict[str, list[str]],
    key: str,
    *,
    build_error: Callable[[str], Exception],
    integer_message: str,
    minimum_message: str,
    default_value: int,
    minimum: int,
) -> int:
    values = query.get(key)
    if not values:
        return default_value
    raw_value = values[0].strip()
    if not raw_value:
        return default_value
    try:
        parsed = int(raw_value)
    except ValueError as exception:
        raise build_error(integer_message) from exception
    if parsed < minimum:
        raise build_error(minimum_message)
    return parsed


def parse_optional_number_strict_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    number_message: str,
    range_message: str,
    min_value: float,
    max_value: float,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise build_error(number_message)
    if isinstance(value, int | float):
        parsed = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise build_error(number_message)
        try:
            parsed = float(stripped)
        except ValueError as exception:
            raise build_error(number_message) from exception
    else:
        raise build_error(number_message)
    if not math.isfinite(parsed):
        raise build_error(number_message)
    if parsed < min_value or parsed > max_value:
        raise build_error(range_message)
    return parsed


def parse_optional_clamped_int_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    number_message: str,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise build_error(number_message)
    if not math.isfinite(float(value)):
        raise build_error(number_message)
    return min(max_value, max(min_value, int(value)))
