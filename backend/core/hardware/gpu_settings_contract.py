"""SoAI - GPU settings field and validation contract [backend/core/hardware/gpu_settings_contract.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "GPU_CLOCK_SETTING_FIELDS",
    "GPU_DIRECT_SETTING_FIELDS",
    "GPU_RANGED_SETTING_FIELDS",
    "GPU_RESET_CLOCKS_FIELD",
    "GPU_SETTINGS_RESET_CONFLICT_MESSAGE",
    "GPU_SETTING_CORE_CLOCK_FIELD",
    "GPU_SETTING_FAN_SPEED_FIELD",
    "GPU_SETTING_FIELDS",
    "GPU_SETTING_MEM_CLOCK_FIELD",
    "GPU_SETTING_POWER_LIMIT_FIELD",
    "extract_direct_gpu_settings",
    "validate_gpu_reset_clock_conflict",
)

GPU_SETTING_POWER_LIMIT_FIELD = "power_limit"
GPU_SETTING_FAN_SPEED_FIELD = "fan_speed"
GPU_SETTING_CORE_CLOCK_FIELD = "core_clock"
GPU_SETTING_MEM_CLOCK_FIELD = "mem_clock"
GPU_DIRECT_SETTING_FIELDS: tuple[str, ...] = (
    GPU_SETTING_POWER_LIMIT_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
)
GPU_RANGED_SETTING_FIELDS: tuple[str, ...] = (
    GPU_SETTING_POWER_LIMIT_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
)
GPU_CLOCK_SETTING_FIELDS: tuple[str, ...] = (
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
)
GPU_RESET_CLOCKS_FIELD = "reset_clocks"
GPU_SETTING_FIELDS: tuple[str, ...] = (*GPU_DIRECT_SETTING_FIELDS, GPU_RESET_CLOCKS_FIELD)
GPU_SETTINGS_RESET_CONFLICT_MESSAGE = (
    "`reset_clocks` cannot be true when clock settings are provided."
)


def validate_gpu_reset_clock_conflict(
    *,
    reset_clocks: bool,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
    message: str = GPU_SETTINGS_RESET_CONFLICT_MESSAGE,
) -> None:
    if reset_clocks and (core_clock is not None or mem_clock is not None):
        raise ValidationError(message)


def extract_direct_gpu_settings(payload: Mapping[str, JSONValue]) -> JSONDict:
    settings_payload: JSONDict = {
        key: payload[key] for key in GPU_DIRECT_SETTING_FIELDS if payload.get(key) is not None
    }
    reset_value = payload.get(GPU_RESET_CLOCKS_FIELD)
    if reset_value is None:
        return settings_payload
    reset_clocks = parse_bool(reset_value, default=False)
    validate_gpu_reset_clock_conflict(
        reset_clocks=reset_clocks,
        core_clock=settings_payload.get(GPU_SETTING_CORE_CLOCK_FIELD),
        mem_clock=settings_payload.get(GPU_SETTING_MEM_CLOCK_FIELD),
    )
    if reset_clocks:
        settings_payload[GPU_RESET_CLOCKS_FIELD] = True
    return settings_payload
