"""SoAI - Hardware preset config parsing and path resolution [backend/app/composition/hardware_preset_configuration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.errors.exceptions import ValidationError
from core.types.json import is_json_value
from core.validation.boolean_coercion import coerce_bool_with_default

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "coerce_hardware_config",
    "resolve_hardware_preset_paths",
)


def coerce_hardware_config(config: ConfigProtocol) -> JSONDict:
    hardware_config_value = config.get("SYSTEM.HARDWARE", {})
    hardware_config: JSONDict = {}
    if isinstance(hardware_config_value, Mapping):
        for key, value in hardware_config_value.items():
            if isinstance(key, str) and is_json_value(value):
                hardware_config[key] = value
    return hardware_config


def resolve_hardware_preset_paths(
    *,
    config: ConfigProtocol,
    base_dir: str,
    hardware_config: JSONDict,
) -> tuple[str, str, bool]:
    system_data_path_value = config.get_str("SYSTEM.PATHS.SYSTEM_DATA")
    if not isinstance(system_data_path_value, str) or not system_data_path_value.strip():
        raise ValidationError(
            "SYSTEM.PATHS.SYSTEM_DATA must be a non-empty string for hardware presets.",
        )
    system_data_path = (
        system_data_path_value
        if os.path.isabs(system_data_path_value)
        else os.path.join(base_dir, system_data_path_value)
    )
    system_data_path = os.path.abspath(system_data_path)
    gpu_slots_path_relative = config.get_str("SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH")
    if not gpu_slots_path_relative:
        raise ValidationError("SYSTEM.HARDWARE.GPU_SETTINGS_SLOTS_PATH must be configured.")
    gpu_slots_path = (
        gpu_slots_path_relative
        if os.path.isabs(gpu_slots_path_relative)
        else os.path.join(base_dir, gpu_slots_path_relative)
    )
    dirty_flag_path = os.path.join(system_data_path, "gpu", "gpu_settings.dirty")
    detailed_gpu_info = coerce_bool_with_default(
        hardware_config.get("DETAILED_GPU_INFO"),
        default=True,
        strict=False,
    )
    return (gpu_slots_path, dirty_flag_path, detailed_gpu_info)
