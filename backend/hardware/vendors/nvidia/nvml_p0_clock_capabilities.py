"""SoAI - NVIDIA NVML P0 clock capability collection [backend/hardware/vendors/nvidia/nvml_p0_clock_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from hardware.gpu_capabilities.payloads import update_control_capability_section
from hardware.vendors.nvidia.internal_protocols import (
    NvmlDeviceGetMinMaxClockOfPStateProtocol,
)
from hardware.vendors.nvidia.nvml_metric_reading import is_nvml_error_not_supported

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = ("apply_p0_default_clocks",)

OPERATION_APPLY_DEFAULT_CLOCK_FROM_P0 = (
    "hardware.vendors.nvidia.nvml_capabilities.apply_default_clock_from_p0"
)

pynvml_module = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


def _apply_default_clock_from_p0(
    *,
    handle: ctypes.c_void_p,
    nvml_device_get_min_max_clock_of_pstate: NvmlDeviceGetMinMaxClockOfPStateProtocol,
    nvml_pstate_0: int,
    clock_type: int,
    caps_key: str,
    gpu_caps: JSONDict,
    logger: TraceLogger,
    operation: str,
) -> int | None:
    active_pynvml_module = pynvml_module
    if active_pynvml_module is None:
        return None
    try:
        p0_result = nvml_device_get_min_max_clock_of_pstate(handle, clock_type, nvml_pstate_0)
        if isinstance(p0_result, tuple) and len(p0_result) >= 2:
            default_value = int(p0_result[1])
            update_control_capability_section(
                gpu_caps,
                caps_key,
                {"default": default_value},
            )
            return default_value
    except active_pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            log_handled_exception(
                logger,
                exception,
                message="NVML P0 clock capability query failed (non-critical).",
                operation=OPERATION_APPLY_DEFAULT_CLOCK_FROM_P0,
                details={"nvml_operation": operation},
                level="trace",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        operation_details = {"nvml_operation": operation}
        log_handled_exception(
            logger,
            exception,
            message="NVML capability query failed (non-critical).",
            operation=OPERATION_APPLY_DEFAULT_CLOCK_FROM_P0,
            level="trace",
            details=operation_details,
        )
    return None


def apply_p0_default_clocks(
    *,
    handle: ctypes.c_void_p,
    gpu_caps: JSONDict,
    logger: TraceLogger,
    nvml_device_get_min_max_clock_of_pstate: NvmlDeviceGetMinMaxClockOfPStateProtocol | None,
    nvml_pstate_0: int | None,
) -> tuple[int | None, int | None]:
    active_pynvml_module = pynvml_module
    if active_pynvml_module is None:
        return (None, None)
    if not isinstance(
        nvml_device_get_min_max_clock_of_pstate,
        NvmlDeviceGetMinMaxClockOfPStateProtocol,
    ) or not isinstance(nvml_pstate_0, int):
        return (None, None)
    try:
        clock_graphics = active_pynvml_module.NVML_CLOCK_GRAPHICS
    except AttributeError:
        clock_graphics = None
    try:
        clock_mem = active_pynvml_module.NVML_CLOCK_MEM
    except AttributeError:
        clock_mem = None
    default_core = (
        _apply_default_clock_from_p0(
            handle=handle,
            nvml_device_get_min_max_clock_of_pstate=nvml_device_get_min_max_clock_of_pstate,
            nvml_pstate_0=nvml_pstate_0,
            clock_type=clock_graphics,
            caps_key="core_clock_mhz",
            gpu_caps=gpu_caps,
            logger=logger,
            operation="read_p0_core_clocks",
        )
        if isinstance(clock_graphics, int)
        else None
    )
    default_mem = (
        _apply_default_clock_from_p0(
            handle=handle,
            nvml_device_get_min_max_clock_of_pstate=nvml_device_get_min_max_clock_of_pstate,
            nvml_pstate_0=nvml_pstate_0,
            clock_type=clock_mem,
            caps_key="mem_clock_mhz",
            gpu_caps=gpu_caps,
            logger=logger,
            operation="read_p0_mem_clocks",
        )
        if isinstance(clock_mem, int)
        else None
    )
    return (default_core, default_mem)
