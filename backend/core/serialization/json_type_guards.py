"""SoAI - Runtime container guards for JSON serialization [backend/core/serialization/json_type_guards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections import defaultdict, deque
from collections.abc import Hashable, Mapping
from typing import TYPE_CHECKING, TypeGuard

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "is_json_defaultdict_candidate",
    "is_json_deque_candidate",
    "is_json_dict_candidate",
    "is_json_mapping_candidate",
    "is_json_pathlike_candidate",
    "is_json_sequence_candidate",
    "is_json_set_candidate",
)


def is_json_mapping_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[Mapping[Hashable, JSONValue]]:
    _ = _value_type
    return isinstance(value, Mapping)


def is_json_dict_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[dict[Hashable, JSONValue]]:
    _ = _value_type
    return isinstance(value, dict)


def is_json_sequence_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[list[JSONValue] | tuple[JSONValue, ...]]:
    _ = _value_type
    return isinstance(value, list | tuple)


def is_json_set_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[set[JSONValue] | frozenset[JSONValue]]:
    _ = _value_type
    return isinstance(value, set | frozenset)


def is_json_defaultdict_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[defaultdict[Hashable, JSONValue]]:
    _ = _value_type
    return isinstance(value, defaultdict)


def is_json_deque_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[deque[JSONValue]]:
    _ = _value_type
    return isinstance(value, deque)


def is_json_pathlike_candidate[T](
    value: T,
    _value_type: type[T] | None = None,
) -> TypeGuard[os.PathLike[str]]:
    _ = _value_type
    return isinstance(value, os.PathLike)
