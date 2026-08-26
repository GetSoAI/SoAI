"""SoAI - MCP argument shape validation primitives [backend/core/mcp/argument_shapes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "optional_trimmed_bounded_string",
    "require_json_dict_value",
    "require_string_map_value",
    "require_string_value",
    "require_trimmed_bounded_string_value",
)


def require_string_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    type_message: str,
) -> str:
    if not isinstance(value, str):
        raise build_error(type_message)
    return value


def require_trimmed_bounded_string_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    type_message: str,
    empty_message: str,
    max_length_message: str,
    max_length: int,
) -> str:
    if not isinstance(value, str):
        raise build_error(type_message)
    normalized = coerce_optional_trimmed_str(value)
    if not normalized:
        raise build_error(empty_message)
    if len(normalized) > max_length:
        raise build_error(max_length_message)
    return normalized


def optional_trimmed_bounded_string(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    type_message: str,
    max_length_message: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise build_error(type_message)
    normalized = coerce_optional_trimmed_str(value)
    if normalized is None:
        return None
    if len(normalized) > max_length:
        raise build_error(max_length_message)
    return normalized


def require_json_dict_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
) -> JSONDict:
    if not is_json_dict(value):
        raise build_error(message)
    return value


def require_string_map_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    object_message: str,
    key_message: str,
    value_message: Callable[[str], str],
) -> dict[str, str]:
    mapping = require_json_dict_value(value, build_error=build_error, message=object_message)
    result: dict[str, str] = {}
    for key, item in mapping.items():
        if not key.strip():
            raise build_error(key_message)
        if not isinstance(item, str):
            raise build_error(value_message(key))
        result[key] = item
    return result
