"""SoAI - Hardware API schemas [backend/features/api/schemas/hardware.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, StrictFloat, StrictInt, model_validator

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import (
    GPU_RESET_CLOCKS_FIELD,
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_FAN_SPEED_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
    GPU_SETTING_POWER_LIMIT_FIELD,
    extract_direct_gpu_settings,
    validate_gpu_reset_clock_conflict,
)
from core.types.json import JSONDict
from features.api.schemas.json_fields import PydanticJSONValue

__all__ = (
    "GPUSettingsRequest",
    "GPUSlotApplyRequest",
    "GPUSlotClearRequest",
    "GPUSlotPreviewRequest",
    "GPUSlotStoreRequest",
    "GPUSlotToggleBootRequest",
    "GPUSoAIBenchStartRequest",
    "KillProcessRequest",
)


class GPUSettingsRequest(BaseModel):
    gpu_id: StrictInt | None = None
    device_id: str | None = None
    power_limit: StrictInt | Literal["auto"] | None = None
    core_clock: StrictInt | Literal["auto"] | None = None
    mem_clock: StrictInt | Literal["auto"] | None = None
    fan_speed: StrictInt | Literal["auto"] | None = None
    reset_clocks: bool = False

    @model_validator(mode="after")
    def check_clock_settings(self) -> GPUSettingsRequest:
        if self.device_id is not None and not self.device_id.strip():
            raise ValidationError("device_id must be a non-empty string.")
        validate_gpu_reset_clock_conflict(
            reset_clocks=self.reset_clocks,
            core_clock=self.core_clock,
            mem_clock=self.mem_clock,
        )
        return self

    def to_gpu_settings_payload(self) -> JSONDict:
        payload: JSONDict = {
            "gpu_id": self.gpu_id,
            "device_id": self.device_id.strip() if self.device_id is not None else None,
            GPU_SETTING_POWER_LIMIT_FIELD: self.power_limit,
            GPU_SETTING_CORE_CLOCK_FIELD: self.core_clock,
            GPU_SETTING_MEM_CLOCK_FIELD: self.mem_clock,
            GPU_SETTING_FAN_SPEED_FIELD: self.fan_speed,
            GPU_RESET_CLOCKS_FIELD: self.reset_clocks,
        }
        device_id = payload.get("device_id")
        if isinstance(device_id, str) and device_id:
            return {"device_id": device_id, **extract_direct_gpu_settings(payload)}
        return payload


class GPUSlotStoreRequest(BaseModel):
    device_id: str
    settings: dict[str, PydanticJSONValue]
    field_modes: dict[str, Literal["auto", "manual"]] | None = None
    apply_at_boot: bool | None = None


class GPUSlotPreviewRequest(BaseModel):
    device_id: str


class GPUSlotApplyRequest(BaseModel):
    device_id: str
    apply_at_boot: bool | None = None


class GPUSlotToggleBootRequest(BaseModel):
    device_id: str
    enabled: bool


class GPUSlotClearRequest(BaseModel):
    device_id: str


class GPUSoAIBenchStartRequest(BaseModel):
    device_id: str
    profile: Literal["standard", "stress"]
    benchmark_mode: Literal["quick", "certified"] | None = None
    temperature_limit_celsius: StrictInt | StrictFloat | None = None


class KillProcessRequest(BaseModel):
    signal: StrictInt = 15
    use_sudo: bool = False
