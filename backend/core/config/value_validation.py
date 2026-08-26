"""SoAI - Runtime config value validation [backend/core/config/value_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING, TypeIs

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue
    from core.types.json import JSONValue

__all__ = (
    "is_config_dict",
    "is_config_value",
)


def is_config_value(value: ConfigValue | JSONValue) -> TypeIs[ConfigValue]:
    if value is None:
        return True
    if isinstance(value, str | int | float | bool | os.PathLike):
        return True
    if isinstance(value, dict):
        return is_config_dict(value)
    if isinstance(value, list):
        return all(is_config_value(item) for item in value)
    if isinstance(value, tuple):
        return all(is_config_value(item) for item in value)
    return False


def is_config_dict(value: ConfigValue | JSONValue) -> TypeIs[ConfigDict]:
    if not isinstance(value, dict):
        return False
    for key, item in value.items():
        if not isinstance(key, str):
            return False
        if not is_config_value(item):
            return False
    return True
