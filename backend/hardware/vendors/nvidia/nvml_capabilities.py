"""SoAI - NVIDIA GPU capabilities collection via NVML [backend/hardware/vendors/nvidia/nvml_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from core.logging.trace import get_logger
from hardware.gpu_capabilities.payloads import build_default_gpu_capabilities
from hardware.vendors.nvidia.discovery import normalize_gpu_name
from hardware.vendors.nvidia.internal_protocols import NvmlDeviceGetNameProtocol
from hardware.vendors.nvidia.nvml_application_clock_capabilities import (
    apply_application_clock_capabilities,
)
from hardware.vendors.nvidia.nvml_capability_sections import (
    apply_fan_capabilities,
    apply_power_capabilities,
    apply_supported_clock_capabilities,
)
from hardware.vendors.nvidia.nvml_p0_clock_capabilities import apply_p0_default_clocks
from hardware.vendors.nvidia.nvml_vf_offset_capabilities import (
    apply_vf_offset_capabilities,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("collect_nvidia_capabilities",)

LOGGER_NAME = "SoAI.hardware.vendors.nvml_capabilities"
OPERATION = "hardware.nvidia.nvml_capabilities.read_gpu_name"


pynvml_module = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


def collect_nvidia_capabilities(handle: ctypes.c_void_p) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    gpu_caps = build_default_gpu_capabilities("NVIDIA GPU")
    active_pynvml_module = pynvml_module
    if active_pynvml_module is None:
        return gpu_caps
    try:
        device_name_function = active_pynvml_module.nvmlDeviceGetName
    except AttributeError:
        device_name_function = None
    if isinstance(device_name_function, NvmlDeviceGetNameProtocol):
        try:
            name_value = device_name_function(handle)
            if isinstance(name_value, str | bytes):
                gpu_caps["name"] = normalize_gpu_name(name_value)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to read NVIDIA GPU name (non-critical).",
                operation=OPERATION,
                level="trace",
            )
    apply_power_capabilities(logger, handle, gpu_caps)
    apply_supported_clock_capabilities(logger, handle, gpu_caps)
    try:
        nvml_device_get_min_max_clock_of_pstate = (
            active_pynvml_module.nvmlDeviceGetMinMaxClockOfPState
        )
    except AttributeError:
        nvml_device_get_min_max_clock_of_pstate = None
    try:
        nvml_pstate_0 = active_pynvml_module.NVML_PSTATE_0
    except AttributeError:
        nvml_pstate_0 = None
    default_core, default_mem = apply_p0_default_clocks(
        handle=handle,
        gpu_caps=gpu_caps,
        logger=logger,
        nvml_device_get_min_max_clock_of_pstate=nvml_device_get_min_max_clock_of_pstate,
        nvml_pstate_0=nvml_pstate_0,
    )
    try:
        clock_graphics_raw = active_pynvml_module.NVML_CLOCK_GRAPHICS
    except AttributeError:
        clock_graphics_raw = None
    try:
        clock_mem_raw = active_pynvml_module.NVML_CLOCK_MEM
    except AttributeError:
        clock_mem_raw = None
    clock_graphics = clock_graphics_raw if isinstance(clock_graphics_raw, int) else None
    clock_mem = clock_mem_raw if isinstance(clock_mem_raw, int) else None
    try:
        core_min_max_offset_reader = active_pynvml_module.nvmlDeviceGetGpcClkMinMaxVfOffset
    except AttributeError:
        core_min_max_offset_reader = None
    try:
        core_current_offset_reader = active_pynvml_module.nvmlDeviceGetGpcClkVfOffset
    except AttributeError:
        core_current_offset_reader = None
    apply_vf_offset_capabilities(
        handle=handle,
        gpu_caps=gpu_caps,
        logger=logger,
        default_clock=default_core,
        legacy_min_max_offset_reader=core_min_max_offset_reader,
        legacy_current_offset_reader=core_current_offset_reader,
        modern_clock_type=clock_graphics,
        pstate=nvml_pstate_0,
        caps_key="core_clock_mhz",
        operation="read_core_vf_offset",
    )
    try:
        mem_min_max_offset_reader = active_pynvml_module.nvmlDeviceGetMemClkMinMaxVfOffset
    except AttributeError:
        mem_min_max_offset_reader = None
    try:
        mem_current_offset_reader = active_pynvml_module.nvmlDeviceGetMemClkVfOffset
    except AttributeError:
        mem_current_offset_reader = None
    apply_vf_offset_capabilities(
        handle=handle,
        gpu_caps=gpu_caps,
        logger=logger,
        default_clock=default_mem,
        legacy_min_max_offset_reader=mem_min_max_offset_reader,
        legacy_current_offset_reader=mem_current_offset_reader,
        modern_clock_type=clock_mem,
        pstate=nvml_pstate_0,
        caps_key="mem_clock_mhz",
        operation="read_mem_vf_offset",
    )
    apply_application_clock_capabilities(
        handle=handle,
        gpu_caps=gpu_caps,
        logger=logger,
    )
    apply_fan_capabilities(logger, handle, gpu_caps)
    return gpu_caps
