"""SoAI - Offline mode configuration parsing and dependency verification [backend/app/cli/offline_mode.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass

from core.bootstrap.offline_mode import read_yaml_boolean_key
from core.config.path_resolution import resolve_config_file_path
from core.errors.exceptions import ConfigurationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

__all__ = (
    "OfflineModeResolver",
    "read_offline_mode_setting",
    "resolve_config_path",
)

OFFLINE_MODE_READ_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
    ValueError,
)


def resolve_config_path(base_dir: str) -> str:
    return resolve_config_file_path(
        base_dir,
        configured_path=os.environ.get("SOAI_CONFIG_PATH", ""),
    )


def read_offline_mode_setting(config_path: str) -> bool | None:
    if not os.path.exists(config_path):
        return None
    try:
        return read_yaml_boolean_key(config_path, key="SYSTEM.RUNTIME.STAY_OFFLINE")
    except OFFLINE_MODE_READ_EXCEPTIONS as exception:
        raise ConfigurationError(
            f"Failed to read config for SYSTEM.RUNTIME.STAY_OFFLINE: {exception}",
        ) from exception


@dataclass(frozen=True, slots=True)
class OfflineModeResolver:
    base_dir: str

    def is_offline_mode_configured(self) -> bool:
        config_path = resolve_config_path(self.base_dir)
        offline_setting = read_offline_mode_setting(config_path)
        return bool(offline_setting)
