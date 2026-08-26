"""SoAI - Runtime configuration factory helpers [backend/core/config/factory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.config.runtime_config import Config

if TYPE_CHECKING:
    from core.config.value_types import ConfigDict

__all__ = (
    "build_config",
    "safe_config_float",
    "safe_config_int",
)


def build_config(
    config_dict: ConfigDict | None = None,
    main_app_base_dir: str | None = None,
) -> Config:
    prepared_config = copy.deepcopy(config_dict) if config_dict is not None else None
    return Config(config_dict=prepared_config, main_app_base_dir=main_app_base_dir)


def safe_config_int(config: ConfigProtocol, key: str) -> int:
    return config.get_int(key)


def safe_config_float(config: ConfigProtocol, key: str) -> float:
    return config.get_float(key)
