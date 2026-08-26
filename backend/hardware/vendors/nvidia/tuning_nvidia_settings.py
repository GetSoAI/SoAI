"""SoAI - NVIDIA GPU fan and clock tuning via nvidia-settings [backend/hardware/vendors/nvidia/tuning_nvidia_settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.hardware.gpu_operation_results import build_gpu_result
from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
from hardware.result_messages import ensure_message_list
from hardware.vendors.nvidia.tuning_nvidia_settings_handlers import (
    apply_nvidia_settings_clock_offsets,
    apply_nvidia_settings_fan_speed,
    apply_nvidia_settings_reset_clocks,
)

if TYPE_CHECKING:
    from core.hardware.protocols import (
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict
    from hardware.vendors.nvidia.smi import NvidiaSettingsController

__all__ = ("sync_set_nvidia_settings_via_nvidia_settings",)

OPERATION_HARDWARE_NVIDIA_TUNING_NVIDIA_SETTINGS_RESET_CLOCKS = (
    "hardware.nvidia.tuning_nvidia_settings.reset_clocks"
)
OPERATION_HARDWARE_NVIDIA_TUNING_NVIDIA_SETTINGS_SET_CLOCKS = (
    "hardware.nvidia.tuning_nvidia_settings.set_clocks"
)
OPERATION_HARDWARE_NVIDIA_TUNING_NVIDIA_SETTINGS_SET_FAN_SPEED = (
    "hardware.nvidia.tuning_nvidia_settings.set_fan_speed"
)


def sync_set_nvidia_settings_via_nvidia_settings(
    logger: TraceLogger | None,
    vendor_id: int,
    nvidia_settings_controller: NvidiaSettingsController | None = None,
    *,
    request: GpuSettingsApplyRequest,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    capabilities: JSONDict | None = None,
) -> JSONDict:
    if not nvml_gate.nvidia_settings_available:
        return build_gpu_result(errors=["nvidia-settings not available on this system."])
    if not nvidia_settings_controller:
        return build_gpu_result(errors=["nvidia-settings controller not initialized."])
    gpu_result = build_gpu_result()
    errors = ensure_message_list(gpu_result, "errors")
    messages = ensure_message_list(gpu_result, "messages")
    caps = capabilities or {}
    if request.power_limit is not None:
        errors.append("Power limit control is not supported by nvidia-settings.")
        capabilities_cache_service.invalidate(vendor_id)
        return gpu_result
    fan_speed = request.fan_speed
    if fan_speed is not None:
        message_count = len(messages)
        if not apply_nvidia_settings_fan_speed(
            logger=logger,
            vendor_id=vendor_id,
            fan_speed=fan_speed,
            errors=errors,
            messages=messages,
            controller=nvidia_settings_controller,
            operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVIDIA_SETTINGS_SET_FAN_SPEED,
        ):
            capabilities_cache_service.invalidate(vendor_id)
            return gpu_result
        if len(messages) > message_count:
            gpu_result["changed"] = True
        if errors:
            capabilities_cache_service.invalidate(vendor_id)
            return gpu_result
    core_clock = request.core_clock
    mem_clock = request.mem_clock
    if request.reset_clocks:
        message_count = len(messages)
        apply_nvidia_settings_reset_clocks(
            logger=logger,
            vendor_id=vendor_id,
            errors=errors,
            messages=messages,
            controller=nvidia_settings_controller,
            operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVIDIA_SETTINGS_RESET_CLOCKS,
        )
        if len(messages) > message_count:
            gpu_result["changed"] = True
    elif core_clock is not None or mem_clock is not None:
        message_count = len(messages)
        if not apply_nvidia_settings_clock_offsets(
            logger=logger,
            vendor_id=vendor_id,
            controller=nvidia_settings_controller,
            core_clock=core_clock,
            mem_clock=mem_clock,
            caps=caps,
            errors=errors,
            messages=messages,
            operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVIDIA_SETTINGS_SET_CLOCKS,
        ):
            capabilities_cache_service.invalidate(vendor_id)
            return gpu_result
        if len(messages) > message_count:
            gpu_result["changed"] = True
    capabilities_cache_service.invalidate(vendor_id)
    return gpu_result
