"""SoAI - JSON value type helpers [backend/core/types/json_value.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue, is_json_value

__all__ = (
    "JSONDict",
    "JSONValue",
    "coerce_json_dict",
    "coerce_json_dict_or_empty",
    "coerce_json_list",
    "coerce_str_dict",
    "coerce_str_list",
    "copy_json_dict",
    "copy_json_dict_list",
    "copy_json_dict_list_map",
    "copy_json_list",
    "copy_json_value",
    "filter_json_dict_list",
    "filter_json_mapping",
    "filter_json_mapping_strict",
    "is_json_value",
    "require_json_dict",
    "require_json_dict_list",
)


def coerce_str_list(
    value: JSONValue,
    *,
    drop_empty: bool = False,
    strip_items: bool = False,
) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            return None
        normalized = entry.strip() if strip_items else entry
        if drop_empty and not normalized:
            continue
        items.append(normalized)
    if drop_empty and not items:
        return None
    return items


def coerce_str_dict(value: JSONValue, *, stringify_values: bool = False) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    entries: dict[str, str] = {}
    for key, raw_value in value.items():
        if not isinstance(key, str):
            if stringify_values:
                continue
            return None
        entry_value = raw_value
        if not isinstance(entry_value, str):
            if not stringify_values:
                return None
            entry_value = str(entry_value)
        entries[key] = entry_value
    return entries


def coerce_json_dict(value: JSONValue) -> JSONDict | None:
    if not is_json_value(value):
        return None
    if not isinstance(value, Mapping):
        return None
    result: JSONDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        if not is_json_value(item):
            return None
        result[key] = item
    return result


def coerce_json_dict_or_empty(value: JSONValue) -> JSONDict:
    if not is_json_value(value):
        return {}
    if not isinstance(value, Mapping):
        return {}
    result: JSONDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return {}
        if not is_json_value(item):
            return {}
        result[key] = item
    return result


def coerce_json_list(value: JSONValue) -> list[JSONValue] | None:
    if not is_json_value(value):
        return None
    if not isinstance(value, list):
        return None
    return copy_json_list(value)


def filter_json_dict_list(value: JSONValue) -> list[JSONDict]:
    if not isinstance(value, list):
        return []
    result: list[JSONDict] = []
    for item in value:
        coerced = coerce_json_dict(item)
        if coerced is not None:
            result.append(coerced)
    return result


def filter_json_mapping[T](value: Mapping[str, T] | None) -> JSONDict:
    if value is None:
        return {}
    result: JSONDict = {}
    for key, item in value.items():
        if isinstance(key, str) and is_json_value(item):
            result[key] = item
    return result


def filter_json_mapping_strict[T](value: Mapping[str, T] | None, *, error_message: str) -> JSONDict:
    if value is None:
        return {}
    result: JSONDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError(error_message)
        if not is_json_value(item):
            raise ValidationError(error_message)
        result[key] = item
    return result


def require_json_dict(value: JSONValue, *, label: str) -> JSONDict:
    if not isinstance(value, Mapping):
        raise ValidationError(
            f"Expected {label} to be a JSON object.",
            details={"type": type(value).__name__},
        )
    result: JSONDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError(
                f"Expected {label} to have string keys.",
                details={"key_type": type(key).__name__},
            )
        if not is_json_value(item):
            raise ValidationError(
                f"Expected {label}.{key} to be JSON-compatible.",
                details={"value_type": type(item).__name__},
            )
        result[key] = item
    return result


def require_json_dict_list(value: JSONValue, *, label: str) -> list[JSONDict]:
    if not isinstance(value, list):
        raise ValidationError(
            f"Expected {label} to be a JSON array.",
            details={"type": type(value).__name__},
        )
    return [require_json_dict(entry, label=label) for entry in value]


def copy_json_value(value: JSONValue) -> JSONValue:
    if isinstance(value, Mapping):
        return copy_json_dict(value)
    if isinstance(value, list):
        return copy_json_list(value)
    return value


def copy_json_dict(value: Mapping[str, JSONValue]) -> JSONDict:
    return {key: copy_json_value(item) for key, item in value.items()}


def copy_json_dict_list(value: Sequence[Mapping[str, JSONValue]]) -> list[JSONDict]:
    return [copy_json_dict(item) for item in value]


def copy_json_dict_list_map(
    value: Mapping[str, Sequence[Mapping[str, JSONValue]]],
) -> dict[str, list[JSONDict]]:
    return {key: copy_json_dict_list(items) for key, items in value.items()}


def copy_json_list(value: Sequence[JSONValue]) -> list[JSONValue]:
    return [copy_json_value(item) for item in value]
