"""SoAI - Bootstrap config scalar readers [backend/core/bootstrap/config_scalars.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from core.config.value_validation import is_config_dict
from core.errors.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue

__all__ = ("read_yaml_scalar_key",)


def read_yaml_scalar_key(config_path: str, *, key: str) -> str | None:
    if not os.path.exists(config_path):
        return None
    parts = _split_dotted_key(key)
    if not parts:
        return None
    config_data = _load_yaml_mapping(config_path)
    if config_data is None:
        return None
    found, value = _resolve_dotted_value(config_data, parts)
    if not found:
        return None
    return _coerce_scalar_value(value, key=key)


def _split_dotted_key(key: str) -> tuple[str, ...]:
    return tuple(part for part in key.split(".") if part)


def _load_yaml_mapping(config_path: str) -> ConfigDict | None:
    yaml_parser = YAML(typ="safe")
    try:
        with open(config_path, encoding="utf-8", errors="strict") as config_file:
            loaded = yaml_parser.load(config_file)
    except YAMLError as exception:
        raise ConfigurationError(f"Config file contains invalid YAML: {config_path}") from exception
    if loaded is None:
        return None
    if not is_config_dict(loaded):
        raise ConfigurationError(f"Config file must contain a YAML mapping: {config_path}")
    return loaded


def _resolve_dotted_value(
    mapping: Mapping[str, ConfigValue],
    parts: tuple[str, ...],
) -> tuple[bool, ConfigValue | None]:
    current: ConfigValue | None = mapping
    for part in parts:
        if not isinstance(current, Mapping):
            return (False, None)
        if part not in current:
            return (False, None)
        current = current[part]
    return (True, current)


def _coerce_scalar_value(value: ConfigValue | None, *, key: str) -> str:
    if value is None:
        raise ConfigurationError(f"{key} must be set to a scalar value in config.yaml.")
    if isinstance(value, str):
        text = value.strip()
    elif isinstance(value, int | float | bool):
        text = str(value).strip()
    else:
        raise ConfigurationError(f"{key} must be set to a scalar value in config.yaml.")
    if not text:
        raise ConfigurationError(f"{key} must be set to a scalar value in config.yaml.")
    return text
