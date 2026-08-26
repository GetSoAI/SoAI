"""SoAI - Bootstrap config value coercion for YAML normalization [backend/app/bootstrap_config_value_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue
    from core.types.json import JSONValue

__all__ = ("coerce_bootstrap_config_value",)


def coerce_bootstrap_config_value(
    value: ConfigValue | JSONValue,
    *,
    config_path: str,
) -> ConfigValue:
    if value is None:
        return None
    if isinstance(value, str | int | float | bool | os.PathLike):
        return value
    if isinstance(value, Mapping):
        resolved: ConfigDict = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ConfigurationError(
                    f"Configuration file at '{config_path}' contains a non-string key: {key!r}",
                )
            resolved[key] = coerce_bootstrap_config_value(item, config_path=config_path)
        return resolved
    if isinstance(value, tuple):
        return tuple(coerce_bootstrap_config_value(item, config_path=config_path) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [coerce_bootstrap_config_value(item, config_path=config_path) for item in value]
    raise ConfigurationError(
        f"Configuration file at '{config_path}' contains an unsupported value: {value!r}",
    )
