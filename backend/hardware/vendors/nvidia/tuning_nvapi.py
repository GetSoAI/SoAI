"""SoAI - NVIDIA GPU tuning via NvAPI [backend/hardware/vendors/nvidia/tuning_nvapi.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_operation_results import build_gpu_result
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.logging.trace import TraceLogger
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import read_control_capability_section
from hardware.gpu_tuning.service_parsing import coerce_auto_or_gpu_setting_int
from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
from hardware.result_messages import (
    append_log_message,
    ensure_message_list,
)
from hardware.vendors.nvidia.nvapi_capabilities import (
    collect_nvapi_capabilities,
    get_nvapi_gpu,
)
from hardware.vendors.nvidia.tuning_error_reporting import (
    report_nvidia_tuning_exception,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_set_nvidia_settings_nvapi",)

OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI = "hardware.nvidia.tuning_nvapi"
OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_RESET_CLOCKS = "hardware.nvidia.tuning_nvapi.reset_clocks"
OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_CLOCKS = "hardware.nvidia.tuning_nvapi.set_clocks"
OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_FAN_SPEED = "hardware.nvidia.tuning_nvapi.set_fan_speed"
OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_POWER_LIMIT = (
    "hardware.nvidia.tuning_nvapi.set_power_limit"
)


def sync_set_nvidia_settings_nvapi(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    request: GpuSettingsApplyRequest,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    capabilities: JSONDict | None = None,
) -> JSONDict:
    nvapi_support = nvml_gate.nvapi_support
    if not nvapi_support.ensure_initialized():
        return build_gpu_result(errors=["NvAPI not available on this platform."])
    gpu_result = build_gpu_result()
    messages = ensure_message_list(gpu_result, "messages")
    errors = ensure_message_list(gpu_result, "errors")
    try:
        nvgpu = get_nvapi_gpu(vendor_id, nvml_gate=nvml_gate)
        if nvgpu is None:
            return build_gpu_result(errors=[f"Could not access GPU {vendor_id} via NvAPI."])
        nvapi_gpu = nvgpu
        fan_speed = request.fan_speed
        if fan_speed is not None:
            try:
                is_auto, fan_value = coerce_auto_or_gpu_setting_int(fan_speed)
                if is_auto:
                    nvapi_support.restore_coolers(nvapi_gpu.handle)
                    message = "Fan control set to AUTO (NvAPI)."
                else:
                    if fan_value is None:
                        raise StateError("Invalid fan speed value.")
                    nvapi_gpu.fan = fan_value
                    message = f"Fan speed set to {fan_speed}% (NvAPI)."
                gpu_result["changed"] = True
                append_log_message(messages, logger, vendor_id, message)
            except RECOVERABLE_EXCEPTIONS as exception:
                if logger is not None:
                    log_handled_exception(
                        logger,
                        exception,
                        message=f"NvAPI fan control failed: {exception}",
                        operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_FAN_SPEED,
                        details={"vendor_id": vendor_id},
                        level="warning",
                    )
                report_nvidia_tuning_exception(
                    vendor_id=vendor_id,
                    errors=errors,
                    exception=exception,
                    message=f"NvAPI fan control failed: {exception}",
                    operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_FAN_SPEED,
                )
                capabilities_cache_service.invalidate(vendor_id)
                return gpu_result
        power_limit = request.power_limit
        if power_limit is not None:
            try:
                is_auto, power_value = coerce_auto_or_gpu_setting_int(power_limit)
                if is_auto:
                    nvapi_gpu.power_limit = 100
                    message = "Power limit reset to default (NvAPI)."
                else:
                    if power_value is None:
                        raise StateError("Invalid power limit value.")
                    nvapi_gpu.power_limit = power_value
                    message = f"Power limit set to {power_limit}% (NvAPI)."
                gpu_result["changed"] = True
                append_log_message(messages, logger, vendor_id, message)
            except RECOVERABLE_EXCEPTIONS as exception:
                if logger is not None:
                    log_handled_exception(
                        logger,
                        exception,
                        message=f"NvAPI power limit failed: {exception}",
                        operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_POWER_LIMIT,
                        details={"vendor_id": vendor_id},
                        level="warning",
                    )
                report_nvidia_tuning_exception(
                    vendor_id=vendor_id,
                    errors=errors,
                    exception=exception,
                    message=f"NvAPI power limit failed: {exception}",
                    operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_POWER_LIMIT,
                )
                capabilities_cache_service.invalidate(vendor_id)
                return gpu_result
        if request.reset_clocks:
            try:
                clocks = nvapi_support.build_clocks(core=0, memory=0)
                if clocks is None:
                    raise StateError("NvAPI clock module is not available.")
                nvapi_gpu.set_overclock(clocks)
                gpu_result["changed"] = True
                message = "Clock offsets reset to 0 (NvAPI)."
                append_log_message(messages, logger, vendor_id, message)
            except RECOVERABLE_EXCEPTIONS as exception:
                if logger is not None:
                    log_handled_exception(
                        logger,
                        exception,
                        message=f"NvAPI clock reset failed: {exception}",
                        operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_RESET_CLOCKS,
                        details={"vendor_id": vendor_id},
                        level="warning",
                    )
                report_nvidia_tuning_exception(
                    vendor_id=vendor_id,
                    errors=errors,
                    exception=exception,
                    message=f"NvAPI clock reset failed: {exception}",
                    operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_RESET_CLOCKS,
                )
                capabilities_cache_service.invalidate(vendor_id)
                return gpu_result
        elif request.core_clock is not None or request.mem_clock is not None:
            try:
                caps = capabilities or collect_nvapi_capabilities(vendor_id, nvml_gate=nvml_gate)
                core_caps = read_control_capability_section(caps, "core_clock_mhz")
                mem_caps = read_control_capability_section(caps, "mem_clock_mhz")
                core_default = coerce_int_from_scalar(core_caps.get("default"))
                mem_default = coerce_int_from_scalar(mem_caps.get("default"))
                if core_default is None or mem_default is None:
                    raise StateError("Default clocks are unavailable for NvAPI clock control.")
                core_current = coerce_int_from_scalar(core_caps.get("current"))
                mem_current = coerce_int_from_scalar(mem_caps.get("current"))

                core_clock = request.core_clock
                mem_clock = request.mem_clock

                if core_clock is not None:
                    if isinstance(core_clock, str) and core_clock.lower() == "auto":
                        core_offset = 0
                    else:
                        core_value = coerce_int_from_scalar(core_clock)
                        if core_value is None:
                            raise StateError("Invalid core clock value.")
                        core_offset = core_value - core_default
                else:
                    if core_current is None:
                        raise StateError(
                            "Cannot preserve current core clock offset; provide core_clock explicitly.",
                        )
                    core_offset = core_current - core_default

                if mem_clock is not None:
                    if isinstance(mem_clock, str) and mem_clock.lower() == "auto":
                        mem_offset = 0
                    else:
                        mem_value = coerce_int_from_scalar(mem_clock)
                        if mem_value is None:
                            raise StateError("Invalid memory clock value.")
                        mem_offset = mem_value - mem_default
                else:
                    if mem_current is None:
                        raise StateError(
                            "Cannot preserve current memory clock offset; provide mem_clock explicitly.",
                        )
                    mem_offset = mem_current - mem_default
                clocks = nvapi_support.build_clocks(core=core_offset, memory=mem_offset)
                if clocks is None:
                    raise StateError("NvAPI clock module is not available.")
                nvapi_gpu.set_overclock(clocks)
                gpu_result["changed"] = True
                message = (
                    "Clock offsets set to Core: "
                    f"{core_offset:+d}MHz, Memory: {mem_offset:+d}MHz (NvAPI)."
                )
                append_log_message(messages, logger, vendor_id, message)
            except RECOVERABLE_EXCEPTIONS as exception:
                if logger is not None:
                    log_handled_exception(
                        logger,
                        exception,
                        message=f"NvAPI clock setting failed: {exception}",
                        operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_CLOCKS,
                        details={"vendor_id": vendor_id},
                        level="warning",
                    )
                report_nvidia_tuning_exception(
                    vendor_id=vendor_id,
                    errors=errors,
                    exception=exception,
                    message=f"NvAPI clock setting failed: {exception}",
                    operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI_SET_CLOCKS,
                )
                capabilities_cache_service.invalidate(vendor_id)
                return gpu_result
    except RECOVERABLE_EXCEPTIONS as exception:
        if logger is not None:
            log_handled_exception(
                logger,
                exception,
                message=f"NvAPI error: {exception}",
                operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI,
                details={"vendor_id": vendor_id},
                level="warning",
            )
        report_nvidia_tuning_exception(
            vendor_id=vendor_id,
            errors=errors,
            exception=exception,
            message=f"NvAPI error: {exception}",
            operation=OPERATION_HARDWARE_NVIDIA_TUNING_NVAPI,
        )
        capabilities_cache_service.invalidate(vendor_id)
    return gpu_result
