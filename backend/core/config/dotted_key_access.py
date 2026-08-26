"""SoAI - Dotted key access for nested config mappings [backend/core/config/dotted_key_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue

__all__ = ("get_nested_config_value",)


def get_nested_config_value(
    mapping: Mapping[str, ConfigValue],
    dotted_key: str,
) -> ConfigValue | None:
    if not isinstance(dotted_key, str) or not dotted_key.strip():
        raise ValidationError("dotted_key must be a non-empty string.")
    current: ConfigValue | None = mapping
    for part in dotted_key.split("."):
        if not part:
            continue
        if not isinstance(current, Mapping):
            return None
        current_mapping: Mapping[str, ConfigValue] = current
        current = current_mapping.get(part)
        if current is None:
            return None
    return current
