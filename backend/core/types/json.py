"""SoAI - JSON-compatible type aliases [backend/core/types/json.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from collections.abc import Hashable, Mapping, Sequence
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    type JSONPrimitive = str | int | float | bool | None
    type JSONValue = JSONPrimitive | Sequence[JSONValue] | Mapping[str, JSONValue]
    type JSONObject = Mapping[str, JSONValue]
    type JSONDict = dict[str, JSONValue]
else:
    JSONPrimitive = str | int | float | bool | None
    JSONValue = JSONPrimitive | Sequence[JSONPrimitive] | Mapping[str, JSONPrimitive]
    JSONObject = Mapping[str, JSONValue]
    JSONDict = dict[str, JSONValue]

__all__ = (
    "is_json_dict",
    "is_json_list",
    "is_json_value",
    "is_str_list",
)


def is_json_value[T](value: T, _value_type: type[T] | None = None) -> TypeGuard[JSONValue]:
    _ = _value_type
    if value is None or isinstance(value, str | int | bool):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if _is_mapping_candidate(value):
        return all(isinstance(key, str) and is_json_value(item) for key, item in value.items())
    if _is_list_candidate(value):
        return all(is_json_value(item) for item in value)
    return False


def is_json_dict[T](value: T, _value_type: type[T] | None = None) -> TypeGuard[JSONDict]:
    _ = _value_type
    if not _is_dict_candidate(value):
        return False
    return all(isinstance(key, str) and is_json_value(item) for key, item in value.items())


def is_json_list[T](value: T, _value_type: type[T] | None = None) -> TypeGuard[list[JSONValue]]:
    _ = _value_type
    if not _is_list_candidate(value):
        return False
    return all(is_json_value(item) for item in value)


def is_str_list[T](value: T, _value_type: type[T] | None = None) -> TypeGuard[list[str]]:
    _ = _value_type
    if not _is_list_candidate(value):
        return False
    return all(isinstance(item, str) for item in value)


def _is_mapping_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[Mapping[Hashable, JSONValue]]:
    _ = _value_type
    return isinstance(value, Mapping)


def _is_dict_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[dict[Hashable, JSONValue]]:
    _ = _value_type
    return isinstance(value, dict)


def _is_list_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[list[JSONValue]]:
    _ = _value_type
    return isinstance(value, list)
