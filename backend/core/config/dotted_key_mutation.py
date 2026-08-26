"""SoAI - Dotted key mutation for nested config mappings [backend/core/config/dotted_key_mutation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from core.config.value_validation import is_config_dict
from core.errors.exceptions import StateError

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue

__all__ = (
    "ensure_nested_mapping",
    "set_nested_config_value",
    "split_config_key",
)


def split_config_key(key: str) -> list[str]:
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Config key must be a non-empty string.")
    parts = [part.strip() for part in key.split(".")]
    if any(not part for part in parts):
        raise ValueError(f"Invalid dotted config key: {key!r}.")
    return parts


def ensure_nested_mapping(source: ConfigDict, key: str) -> ConfigDict:
    parts = split_config_key(key)
    current: MutableMapping[str, ConfigValue] = source
    for index, part in enumerate(parts):
        is_final = index == len(parts) - 1
        if not isinstance(current, MutableMapping):
            raise ValueError(f"Cannot ensure mapping at '{key}': parent is not a mapping.")
        if is_final:
            existing = current.get(part)
            if existing is None:
                new_mapping: ConfigDict = {}
                current[part] = new_mapping
                return new_mapping
            if is_config_dict(existing):
                return existing
            raise ValueError(f"Cannot ensure mapping at '{key}': existing value is not a mapping.")
        next_value = current.get(part)
        if next_value is None:
            next_mapping: ConfigDict = {}
            current[part] = next_mapping
            current = next_mapping
            continue
        if is_config_dict(next_value):
            current = next_value
            continue
        raise ValueError(f"Cannot ensure mapping at '{key}': '{part}' is not a mapping.")
    raise StateError("Unreachable: ensure_nested_mapping did not resolve.")


def set_nested_config_value(source: ConfigDict, key: str, value: ConfigValue) -> None:
    parts = split_config_key(key)
    current: MutableMapping[str, ConfigValue] = source
    for part in parts[:-1]:
        if not isinstance(current, MutableMapping):
            raise ValueError(f"Cannot set '{key}': parent for '{part}' is not a mapping.")
        existing = current.get(part)
        if existing is None:
            next_mapping: ConfigDict = {}
            current[part] = next_mapping
            current = next_mapping
            continue
        if is_config_dict(existing):
            current = existing
            continue
        raise ValueError(f"Cannot set '{key}': '{part}' exists but is not a mapping.")
    if not isinstance(current, MutableMapping):
        raise ValueError(f"Cannot set '{key}': parent is not a mapping.")
    current[parts[-1]] = value
