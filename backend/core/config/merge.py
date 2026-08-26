"""SoAI - Config mapping merge and dot-notation expansion primitives [backend/core/config/merge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.value_types import ConfigValue
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "deep_merge",
    "deep_merge_config",
    "expand_dot_notation",
)


def expand_dot_notation(flat_dict: Mapping[str, JSONValue]) -> JSONDict:
    result: JSONDict = {}
    for raw_key, value in flat_dict.items():
        if "." not in raw_key:
            result[raw_key] = value
            continue
        parts = [part for part in raw_key.split(".") if part]
        if not parts:
            continue
        current: JSONDict = result
        for part in parts[:-1]:
            existing = current.get(part)
            if existing is None:
                next_level: JSONDict = {}
                current[part] = next_level
                current = next_level
                continue
            if not isinstance(existing, dict):
                raise ValidationError(
                    f"Cannot expand dot notation key '{raw_key}' because '{part}' is not a mapping.",
                )
            current = existing
        leaf = parts[-1]
        existing_leaf = current.get(leaf)
        if isinstance(existing_leaf, dict) and isinstance(value, Mapping):
            sanitized: JSONDict = {}
            for key, item in value.items():
                if isinstance(key, str):
                    sanitized[key] = item
            current[leaf] = deep_merge(existing_leaf, sanitized, expand_dots=False)
        else:
            current[leaf] = value
    return result


def deep_merge(
    old_dict: JSONDict,
    new_dict: Mapping[str, JSONValue],
    expand_dots: bool = True,
) -> JSONDict:
    if expand_dots:
        new_dict = expand_dot_notation(new_dict)
    for key, value in new_dict.items():
        if (
            isinstance(value, Mapping)
            and key in old_dict
            and isinstance(old_dict.get(key), Mapping)
        ):
            existing_value = old_dict[key]
            if isinstance(existing_value, dict):
                deep_merge(existing_value, value, expand_dots=False)
            else:
                old_dict[key] = deep_merge({}, value, expand_dots=False)
        else:
            old_dict[key] = value
    return old_dict


def deep_merge_config(
    old_dict: MutableMapping[str, ConfigValue],
    new_dict: Mapping[str, JSONValue],
    expand_dots: bool = True,
) -> MutableMapping[str, ConfigValue]:
    if expand_dots:
        new_dict = expand_dot_notation(new_dict)
    for key, value in new_dict.items():
        existing = old_dict.get(key)
        if isinstance(value, Mapping) and isinstance(existing, MutableMapping):
            deep_merge_config(existing, value, expand_dots=False)
        else:
            old_dict[key] = value
    return old_dict
