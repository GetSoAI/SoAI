"""SoAI - Runtime configuration object with path normalization [backend/core/config/runtime_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import os
from typing import TYPE_CHECKING, overload, override

from core.config.dotted_key_access import get_nested_config_value
from core.config.dotted_key_mutation import (
    ensure_nested_mapping,
    set_nested_config_value,
)
from core.config.layout import (
    BASE_DOTTED_KEYS,
    BASE_PATH_KEY,
    STATE_DOTTED_KEYS,
    apply_config_layout,
    resolve_base_path,
)
from core.config.path_resolution import ConfigPathResolutionError
from core.config.protocols import ConfigProtocol
from core.config.value_validation import is_config_dict
from core.errors.exceptions import ConfigurationError
from core.logging.trace import get_logger
from core.meta.paths import get_repo_root
from core.validation.booleans import parse_bool_flag_or_none

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict, ConfigValue

__all__ = (
    "BASE_DOTTED_KEYS",
    "CONFIG_LAYOUT_DOTTED_KEYS",
    "STATE_DOTTED_KEYS",
    "Config",
    "ConfigError",
)

LOGGER_NAME = "SoAI.core.config.runtime_config"
CONFIG_LAYOUT_DOTTED_KEYS = (STATE_DOTTED_KEYS, BASE_DOTTED_KEYS)


class ConfigError(ConfigurationError): ...


class Config(ConfigProtocol):
    def __init__(
        self,
        config_dict: ConfigDict | None = None,
        main_app_base_dir: str | None = None,
    ) -> None:
        if config_dict is not None and not is_config_dict(config_dict):
            raise ConfigError("Provided config_dict contains unsupported values.")
        self._config: ConfigDict = config_dict if config_dict is not None else {}
        self._main_app_base_dir = main_app_base_dir
        self._default_base_path = self._infer_default_base_path()
        self._base_path = self._default_base_path
        self._apply_config(self._config)

    @staticmethod
    def _infer_default_base_path() -> str:
        return get_repo_root()

    def _resolve_base_path(self, candidate: str | os.PathLike[str]) -> str:
        try:
            resolved = resolve_base_path(
                default_base_path=self._default_base_path,
                configured_base_path=candidate,
                main_app_base_dir=None,
            )
        except ConfigPathResolutionError as exception:
            raise ConfigError(str(exception)) from exception
        return resolved

    def _apply_config(self, target_config: ConfigDict) -> None:
        try:
            configured_base_value = get_nested_config_value(target_config, BASE_PATH_KEY)
            configured_base_path = (
                configured_base_value
                if isinstance(configured_base_value, str | os.PathLike)
                else None
            )
            self._base_path = resolve_base_path(
                default_base_path=self._default_base_path,
                configured_base_path=configured_base_path,
                main_app_base_dir=self._main_app_base_dir,
            )
            _ = apply_config_layout(target_config, base_path=self._base_path)
        except ConfigPathResolutionError as exception:
            raise ConfigError(str(exception)) from exception

    @overload
    def get(self, key: str, default: ConfigValue) -> ConfigValue: ...

    @overload
    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None: ...

    @override
    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None:
        try:
            if not isinstance(key, str) or not key:
                return default
            value: ConfigValue | None = self._config
            for part in key.split("."):
                if not is_config_dict(value):
                    return default
                if part not in value:
                    return default
                value = value[part]
            return value
        except (AttributeError, KeyError, TypeError):
            return default

    @override
    def get_int(self, key: str, default: int = 0) -> int:
        value = self.get(key, default)
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, os.PathLike):
            value = os.fspath(value)
        if value is None or not isinstance(value, str | float | int):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            logger = get_logger(LOGGER_NAME)
            logger.warning("Config %s=%r invalid int, using default %s", key, value, default)
            return default

    @override
    def get_float(self, key: str, default: float = 0.0) -> float:
        value = self.get(key, default)
        if isinstance(value, bool):
            return default
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, os.PathLike):
            value = os.fspath(value)
        if value is None or not isinstance(value, str):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            logger = get_logger(LOGGER_NAME)
            logger.warning(
                "Config %s=%r invalid float, using default %s",
                key,
                repr(value),
                default,
            )
            return default

    @override
    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        parsed = parse_bool_flag_or_none(value)
        if parsed is not None:
            return bool(parsed)
        logger = get_logger(LOGGER_NAME)
        logger.warning(
            "Config %s=%r invalid bool, using default %s",
            key,
            repr(value),
            default,
        )
        return default

    @overload
    def get_str(self, key: str, default: str) -> str: ...

    @overload
    def get_str(self, key: str, default: str | None = None) -> str | None: ...

    @override
    def get_str(self, key: str, default: str | None = None) -> str | None:
        value = self.get(key, default)
        if value is None:
            return default
        if isinstance(value, str):
            return value
        if isinstance(value, os.PathLike):
            return os.fspath(value)
        logger = get_logger(LOGGER_NAME)
        logger.warning(
            "Config %s=%r invalid str, using default %s",
            key,
            repr(value),
            default,
        )
        return default

    @override
    def require_str(self, key: str) -> str:
        value = self.get_str(key)
        if value is None:
            raise ConfigError(f"Missing required string config value: {key!r}.")
        stripped = value.strip()
        if not stripped:
            raise ConfigError(f"Empty required string config value: {key!r}.")
        return stripped

    @override
    def require_str_value(self, key: str) -> str:
        value = self.get(key)
        if value is None:
            raise ConfigError(f"Missing required string config value: {key!r}.")
        if isinstance(value, str):
            return value
        if isinstance(value, os.PathLike):
            return os.fspath(value)
        raise ConfigError(
            f"Required string config value {key!r} has invalid type {type(value).__name__}.",
        )

    def update(self, new_config: ConfigDict) -> None:
        if not is_config_dict(new_config):
            raise ConfigError("Provided config_dict contains unsupported values.")
        self._config.update(new_config)
        base_candidate = get_nested_config_value(new_config, BASE_PATH_KEY)
        if base_candidate is not None:
            if not isinstance(base_candidate, str | os.PathLike):
                raise ConfigError("SYSTEM.PATHS.BASE must be a string or os.PathLike.")
            self._base_path = self._resolve_base_path(base_candidate)
        try:
            _ = apply_config_layout(self._config, base_path=self._base_path)
        except ConfigPathResolutionError as exception:
            raise ConfigError(str(exception)) from exception

    def replace(self, new_dict: ConfigDict) -> None:
        if new_dict is self._config:
            self._apply_config(self._config)
            return
        candidate = copy.deepcopy(new_dict)
        self._apply_config(candidate)
        self._config.clear()
        self._config.update(candidate)

    def ensure_mapping(self, key: str) -> ConfigDict:
        try:
            return ensure_nested_mapping(self._config, key)
        except ValueError as exception:
            raise ConfigError(str(exception)) from exception

    def set_value(self, key: str, value: ConfigValue) -> None:
        try:
            set_nested_config_value(self._config, key, value)
        except ValueError as exception:
            raise ConfigError(str(exception)) from exception
