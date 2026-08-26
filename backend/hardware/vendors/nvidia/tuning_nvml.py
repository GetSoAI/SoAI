"""SoAI - NVIDIA GPU power and clock tuning via NVML [backend/hardware/vendors/nvidia/tuning_nvml.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.hardware.gpu_operation_results import build_gpu_result
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from core.imports.availability import module_available
from core.logging.trace import TraceLogger
from core.types.json import JSONDict
from hardware.gpu_tuning.settings_request import GpuSettingsApplyRequest
from hardware.result_messages import ensure_message_list
from hardware.vendors.nvidia.internal_protocols import (
    NvmlDeviceGetHandleByIndexProtocol,
)
from hardware.vendors.nvidia.nvml_power_limit_resolution import (
    resolve_nvml_power_limit_functions,
)
from hardware.vendors.nvidia.tuning_nvml_clock_offsets import apply_nvml_clock_settings
from hardware.vendors.nvidia.tuning_nvml_controls import apply_nvml_fan_setting
from hardware.vendors.nvidia.tuning_power_limit import apply_nvml_power_limit_setting

__all__ = ("sync_set_nvidia_settings_via_nvml",)

OPERATION_SET_NVIDIA_PERSISTENCE_MODE = "hardware.vendors.nvidia.tuning_nvml.set_persistence_mode"

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def _pynvml_available() -> bool:
    return pynvml_module_ref is not None


def sync_set_nvidia_settings_via_nvml(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    request: GpuSettingsApplyRequest,
    nvml_gate: NvmlGateProtocol,
    capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    capabilities: JSONDict | None = None,
) -> JSONDict:
    gpu_result = build_gpu_result()
    messages = ensure_message_list(gpu_result, "messages")
    errors = ensure_message_list(gpu_result, "errors")
    if not _pynvml_available() or not nvml_gate.nvml_available:
        errors.append("pynvml/NVML is unavailable on this system.")
        return gpu_result
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("pynvml/NVML is unavailable on this system.")
        return gpu_result
    try:
        with nvml_gate.session():
            try:
                device_get_handle_by_index = pynvml_module.nvmlDeviceGetHandleByIndex
            except AttributeError:
                device_get_handle_by_index = None
            if not isinstance(device_get_handle_by_index, NvmlDeviceGetHandleByIndexProtocol):
                raise StateError(
                    "NVML functions are not callable. This indicates a corrupted pynvml installation.",
                    operation="hardware_nvidia.sync_set_nvidia_settings",
                )
            handle = device_get_handle_by_index(vendor_id)
            try:
                device_set_gpc_clk_vf_offset = pynvml_module.nvmlDeviceSetGpcClkVfOffset
            except AttributeError:
                device_set_gpc_clk_vf_offset = None
            try:
                device_set_mem_clk_vf_offset = pynvml_module.nvmlDeviceSetMemClkVfOffset
            except AttributeError:
                device_set_mem_clk_vf_offset = None
            try:
                clock_graphics_raw = pynvml_module.NVML_CLOCK_GRAPHICS
            except AttributeError:
                clock_graphics_raw = None
            try:
                clock_mem_raw = pynvml_module.NVML_CLOCK_MEM
            except AttributeError:
                clock_mem_raw = None
            try:
                pstate_0_raw = pynvml_module.NVML_PSTATE_0
            except AttributeError:
                pstate_0_raw = None
            clock_graphics = clock_graphics_raw if isinstance(clock_graphics_raw, int) else None
            clock_mem = clock_mem_raw if isinstance(clock_mem_raw, int) else None
            pstate_0 = pstate_0_raw if isinstance(pstate_0_raw, int) else None
            try:
                device_set_persistence_mode = pynvml_module.nvmlDeviceSetPersistenceMode
            except AttributeError:
                device_set_persistence_mode = None
            try:
                feature_enabled = pynvml_module.NVML_FEATURE_ENABLED
            except AttributeError:
                feature_enabled = None
            try:
                nvml_error_not_supported = pynvml_module.NVML_ERROR_NOT_SUPPORTED
            except AttributeError:
                nvml_error_not_supported = None
            if callable(device_set_persistence_mode) and isinstance(feature_enabled, int):
                try:
                    device_set_persistence_mode(handle, feature_enabled)
                except pynvml_module.NVMLError as exception:
                    try:
                        exception_value = exception.value
                    except AttributeError:
                        exception_value = None
                    if exception_value != nvml_error_not_supported:
                        if logger:
                            log_handled_exception(
                                logger,
                                exception,
                                message="Could not set persistence mode for GPU.",
                                operation=OPERATION_SET_NVIDIA_PERSISTENCE_MODE,
                                details={"vendor_id": vendor_id},
                                level="trace",
                            )
            power_limit = request.power_limit
            if power_limit is not None:
                try:
                    power_default_limit_function, power_set_limit_function = (
                        resolve_nvml_power_limit_functions(pynvml_module)
                    )
                    apply_nvml_power_limit_setting(
                        logger,
                        vendor_id=vendor_id,
                        messages=messages,
                        handle=handle,
                        power_limit=power_limit,
                        power_default_limit_function=power_default_limit_function,
                        power_set_limit_function=power_set_limit_function,
                    )
                    gpu_result["changed"] = True
                except (ValueError, pynvml_module.NVMLError, RuntimeError) as exception:
                    errors.append(f"Failed to set power limit: {exception}")
                    capabilities_cache_service.invalidate(vendor_id)
                    return gpu_result
            fan_speed = request.fan_speed
            if fan_speed is not None:
                if apply_nvml_fan_setting(
                    logger,
                    vendor_id,
                    messages=messages,
                    errors=errors,
                    handle=handle,
                    fan_speed=fan_speed,
                ):
                    gpu_result["changed"] = True
                if errors:
                    capabilities_cache_service.invalidate(vendor_id)
                    return gpu_result
            if apply_nvml_clock_settings(
                logger,
                vendor_id,
                messages=messages,
                errors=errors,
                handle=handle,
                reset_clocks=request.reset_clocks,
                core_clock=request.core_clock,
                mem_clock=request.mem_clock,
                device_set_gpc_clk_vf_offset=device_set_gpc_clk_vf_offset,
                device_set_mem_clk_vf_offset=device_set_mem_clk_vf_offset,
                modern_core_clock_type=clock_graphics,
                modern_mem_clock_type=clock_mem,
                modern_pstate=pstate_0,
                capabilities=capabilities,
            ):
                gpu_result["changed"] = True
    except pynvml_module.NVMLError as exception:
        errors.append(
            f"A critical NVML error occurred: {exception}. This is likely a driver or permission issue.",
        )
    capabilities_cache_service.invalidate(vendor_id)
    return gpu_result
