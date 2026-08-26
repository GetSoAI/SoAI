"""SoAI - Plugin SDK configuration with path resolution [backend/plugin_sdk/config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.config.layout import (
    BASE_DOTTED_KEYS,
    BASE_PATH_KEY,
    STATE_DOTTED_KEYS,
)
from core.config.runtime_config import CONFIG_LAYOUT_DOTTED_KEYS, Config, ConfigError
from core.config.value_validation import is_config_dict, is_config_value

__all__ = (
    "BASE_DOTTED_KEYS",
    "BASE_PATH_KEY",
    "CONFIG_LAYOUT_DOTTED_KEYS",
    "STATE_DOTTED_KEYS",
    "Config",
    "ConfigError",
    "is_config_dict",
    "is_config_value",
)
