"""SoAI - MCP argument validation primitives [backend/core/mcp/argument_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence

from core.types.json import JSONDict, JSONValue, is_json_dict
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "optional_trimmed_string",
    "parse_optional_bool_strict_value",
    "parse_string_or_unique_non_empty_string_list_value",
    "require_json_dict_list_argument",
    "require_no_unknown_keys",
    "require_non_empty_string_value",
    "require_unique_non_empty_string_list_argument",
    "unknown_keys",
)


def unknown_keys(arguments: JSONDict, allowed_keys: Collection[str]) -> tuple[str, ...]:
    return tuple(sorted(key for key in arguments if key not in allowed_keys))


def require_no_unknown_keys(
    arguments: JSONDict,
    allowed_keys: Collection[str],
    *,
    build_error: Callable[[str], Exception],
    message: Callable[[tuple[str, ...]], str],
) -> None:
    invalid_keys = unknown_keys(arguments, allowed_keys)
    if invalid_keys:
        raise build_error(message(invalid_keys))


def require_non_empty_string_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    type_message: str,
    empty_message: str,
) -> str:
    if not isinstance(value, str):
        raise build_error(type_message)
    normalized = coerce_optional_trimmed_str(value)
    if not normalized:
        raise build_error(empty_message)
    return normalized


def optional_trimmed_string(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    type_message: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise build_error(type_message)
    return coerce_optional_trimmed_str(value)


def parse_optional_bool_strict_value(
    value: JSONValue,
    *,
    build_error: Callable[[str], Exception],
    message: str,
) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise build_error(message)
    return bool(value)


def parse_string_or_unique_non_empty_string_list_value(
    value: JSONValue,
    *,
    default: Sequence[str],
    allowed_values: Collection[str],
    build_error: Callable[[str], Exception],
    list_message: str,
    entry_message: str,
    empty_message: str,
    unknown_message: Callable[[str], str],
) -> list[str]:
    values_list: list[str]
    if value is None:
        return list(default)
    if isinstance(value, str):
        values_list = [value.strip()] if value.strip() else []
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        values_list = []
        for item in value:
            if not isinstance(item, str):
                raise build_error(entry_message)
            stripped = item.strip()
            if stripped:
                values_list.append(stripped)
    else:
        raise build_error(list_message)
    result: list[str] = []
    for item in values_list:
        if item not in allowed_values:
            raise build_error(unknown_message(item))
        if item not in result:
            result.append(item)
    if not result:
        raise build_error(empty_message)
    return result


def require_json_dict_list_argument(
    arguments: JSONDict,
    key: str,
    *,
    build_error: Callable[[str], Exception],
) -> list[JSONDict]:
    if key not in arguments:
        return []
    value = arguments[key]
    if not isinstance(value, list):
        raise build_error(f"{key} must be an array.")
    result: list[JSONDict] = []
    for index, item in enumerate(value):
        if not is_json_dict(item):
            raise build_error(f"{key}[{index}] must be an object.")
        result.append(item)
    return result


def require_unique_non_empty_string_list_argument(
    arguments: JSONDict,
    key: str,
    *,
    build_error: Callable[[str], Exception],
) -> list[str]:
    if key not in arguments:
        return []
    value = arguments[key]
    if not isinstance(value, list):
        raise build_error(f"{key} must be an array.")
    result: list[str] = []
    seen_values: set[str] = set()
    for index, item in enumerate(value):
        item_label = f"{key}[{index}]"
        normalized = require_non_empty_string_value(
            item,
            build_error=build_error,
            type_message=f"{item_label} must be a non-empty string.",
            empty_message=f"{item_label} must be a non-empty string.",
        )
        if normalized in seen_values:
            raise build_error(f"{key}[{index}] duplicates '{normalized}'.")
        seen_values.add(normalized)
        result.append(normalized)
    return result
