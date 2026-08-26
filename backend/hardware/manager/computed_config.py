"""SoAI - Hardware manager computed configuration [backend/hardware/manager/computed_config.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.history.config_view import build_history_config_view
from core.validation.booleans import parse_bool
from hardware.manager.dependencies import HardwareManagerDependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "HardwareManagerComputedConfig",
    "compute_hardware_manager_config",
)


@dataclass(frozen=True, slots=True)
class HardwareManagerComputedConfig:
    config_dict: JSONDict
    db_retention_hours: int
    history_enabled: bool
    base_dir: str


def compute_hardware_manager_config(
    deps: HardwareManagerDependencies,
) -> HardwareManagerComputedConfig:
    config_dict = dict(deps.config)
    history_config = deps.settings.history_config
    history_view = build_history_config_view(
        history_config,
        enabled_default=False,
        logging_interval_default=1,
        max_points_default=1,
        retention_hours_default=0,
        supported_intervals_default=(),
        supported_aggregations_default=(),
        default_interval_default=1,
    )
    db_retention_hours = history_view.retention_hours
    history_enabled = bool(deps.database_hardware) and parse_bool(
        history_view.enabled,
        default=False,
    )
    base_dir = deps.base_path or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return HardwareManagerComputedConfig(
        config_dict=config_dict,
        db_retention_hours=db_retention_hours,
        history_enabled=history_enabled,
        base_dir=base_dir,
    )
