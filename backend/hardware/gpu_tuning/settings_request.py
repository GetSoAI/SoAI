"""SoAI - GPU settings apply request model [backend/hardware/gpu_tuning/settings_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.hardware.gpu_settings_contract import (
    GPU_RESET_CLOCKS_FIELD,
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
    GPU_SETTING_POWER_LIMIT_FIELD,
)
from core.validation.booleans import parse_bool

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "GpuSettingsApplyRequest",
    "build_gpu_settings_apply_request",
)


@dataclass(frozen=True, slots=True)
class GpuSettingsApplyRequest:
    control_backend: str | None = None
    power_limit: JSONValue | None = None
    fan_speed: JSONValue | None = None
    core_clock: JSONValue | None = None
    mem_clock: JSONValue | None = None
    reset_clocks: bool = False


def build_gpu_settings_apply_request(
    settings: Mapping[str, JSONValue],
    *,
    control_backend: str | None = None,
) -> GpuSettingsApplyRequest:
    return GpuSettingsApplyRequest(
        control_backend=control_backend,
        power_limit=settings.get(GPU_SETTING_POWER_LIMIT_FIELD),
        fan_speed=settings.get(GPU_SETTING_FAN_SPEED_FIELD),
        core_clock=settings.get(GPU_SETTING_CORE_CLOCK_FIELD),
        mem_clock=settings.get(GPU_SETTING_MEM_CLOCK_FIELD),
        reset_clocks=bool(parse_bool(settings.get(GPU_RESET_CLOCKS_FIELD), default=False)),
    )
