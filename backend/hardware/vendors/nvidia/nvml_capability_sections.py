"""SoAI - NVIDIA NVML capability section loaders [backend/hardware/vendors/nvidia/nvml_capability_sections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from hardware.gpu_capabilities.payloads import update_control_capability_section
from hardware.vendors.nvidia.nvml_metric_reading import is_nvml_error_not_supported
from hardware.vendors.nvidia.nvml_power_limit_resolution import (
    resolve_nvml_power_limit_functions,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = (
    "apply_fan_capabilities",
    "apply_power_capabilities",
    "apply_supported_clock_capabilities",
)

OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_FAN_SPEED = (
    "hardware.nvidia.nvml_capabilities.read_fan_speed"
)
OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_GRAPHICS_CLOCKS = (
    "hardware.nvidia.nvml_capabilities.read_graphics_clocks"
)
OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_POWER_LIMITS = (
    "hardware.nvidia.nvml_capabilities.read_power_limits"
)
OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_SUPPORTED_CLOCKS = (
    "hardware.nvidia.nvml_capabilities.read_supported_clocks"
)
POWER_CAPABILITY_READ_EXCEPTIONS: tuple[type[Exception], ...] = (
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def apply_power_capabilities(
    logger: TraceLogger,
    handle: ctypes.c_void_p,
    gpu_caps: JSONDict,
) -> None:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        return
    try:
        limits_function = pynvml_module.nvmlDeviceGetPowerManagementLimitConstraints
    except AttributeError:
        limits_function = None
    try:
        default_limit_function = pynvml_module.nvmlDeviceGetPowerManagementDefaultLimit
    except AttributeError:
        default_limit_function = None
    try:
        current_limit_function = pynvml_module.nvmlDeviceGetPowerManagementLimit
    except AttributeError:
        current_limit_function = None
    _default_setter_function, set_limit_function = resolve_nvml_power_limit_functions(
        pynvml_module,
    )
    if not (
        callable(limits_function)
        and callable(default_limit_function)
        and callable(current_limit_function)
        and set_limit_function is not None
    ):
        return
    try:
        limits = limits_function(handle)
        if not isinstance(limits, list | tuple) or len(limits) < 2:
            raise StateError("Invalid power limits returned")
        min_power_limit, max_power_limit = (int(limits[0]), int(limits[1]))
        default_raw = default_limit_function(handle)
        current_raw = current_limit_function(handle)
        update_control_capability_section(
            gpu_caps,
            "power_limit_watts",
            {
                "min": min_power_limit // 1000,
                "max": max_power_limit // 1000,
                "default": int(default_raw) // 1000 if isinstance(default_raw, int | float) else 0,
                "current": int(current_raw) // 1000 if isinstance(current_raw, int | float) else 0,
                "supported": min_power_limit < max_power_limit,
                "via_nvml": True,
            },
        )
    except pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            log_handled_exception(
                logger,
                exception,
                message="Failed to read NVIDIA power limits (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_POWER_LIMITS,
                level="trace",
            )
    except POWER_CAPABILITY_READ_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA power limits (non-critical).",
            operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_POWER_LIMITS,
            level="trace",
        )


def apply_fan_capabilities(
    logger: TraceLogger,
    handle: ctypes.c_void_p,
    gpu_caps: JSONDict,
) -> None:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        return
    try:
        fan_speed_function = pynvml_module.nvmlDeviceGetFanSpeed
    except AttributeError:
        fan_speed_function = None
    try:
        default_fan_speed_function = pynvml_module.nvmlDeviceSetDefaultFanSpeed_v2
    except AttributeError:
        default_fan_speed_function = None
    try:
        set_fan_speed_function = pynvml_module.nvmlDeviceSetFanSpeed_v2
    except AttributeError:
        set_fan_speed_function = None
    if not callable(fan_speed_function):
        return
    try:
        fan_value_raw = fan_speed_function(handle)
        update_control_capability_section(
            gpu_caps,
            "fan_speed_percent",
            {
                "current": int(fan_value_raw) if isinstance(fan_value_raw, int | float) else 0,
                "supported": callable(default_fan_speed_function)
                and callable(set_fan_speed_function),
                "via_nvml": True,
            },
        )
    except pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            log_handled_exception(
                logger,
                exception,
                message="Failed to read NVIDIA fan speed (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_FAN_SPEED,
                level="trace",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA fan speed (non-critical).",
            operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_FAN_SPEED,
            level="trace",
        )


def apply_supported_clock_capabilities(
    logger: TraceLogger,
    handle: ctypes.c_void_p,
    gpu_caps: JSONDict,
) -> tuple[int | None, int | None]:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        return (None, None)
    mem_min: int | None = None
    mem_max: int | None = None
    try:
        memory_clocks_function = pynvml_module.nvmlDeviceGetSupportedMemoryClocks
    except AttributeError:
        memory_clocks_function = None
    try:
        graphics_clocks_function = pynvml_module.nvmlDeviceGetSupportedGraphicsClocks
    except AttributeError:
        graphics_clocks_function = None
    if not (callable(memory_clocks_function) and callable(graphics_clocks_function)):
        return (None, None)
    try:
        mem_clocks = memory_clocks_function(handle)
        if not isinstance(mem_clocks, Sequence):
            return (None, None)
        mem_values = [int(clock) for clock in mem_clocks]
        mem_min, mem_max = (min(mem_values), max(mem_values))
        update_control_capability_section(
            gpu_caps,
            "mem_clock_mhz",
            {"min": mem_min, "max": mem_max},
        )
        all_core_clocks: set[int] = set()
        for mem_clock in mem_values:
            try:
                clocks = graphics_clocks_function(handle, mem_clock)
                if isinstance(clocks, Sequence):
                    all_core_clocks.update(int(clock) for clock in clocks)
            except pynvml_module.NVMLError as exception:
                if not is_nvml_error_not_supported(exception):
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to read graphics clocks for memory clock (non-critical).",
                        operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_GRAPHICS_CLOCKS,
                        details={"mem_clock_mhz": mem_clock},
                        level="trace",
                    )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to read graphics clocks for memory clock (non-critical).",
                    operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_GRAPHICS_CLOCKS,
                    details={"mem_clock_mhz": mem_clock},
                    level="trace",
                )
        if all_core_clocks:
            core_values = sorted(all_core_clocks)
            update_control_capability_section(
                gpu_caps,
                "core_clock_mhz",
                {"min": core_values[0], "max": core_values[-1]},
            )
    except pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            log_handled_exception(
                logger,
                exception,
                message="Failed to read NVIDIA supported clock information (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_SUPPORTED_CLOCKS,
                level="trace",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to read NVIDIA supported clock information (non-critical).",
            operation=OPERATION_HARDWARE_NVIDIA_NVML_CAPABILITIES_READ_SUPPORTED_CLOCKS,
            level="trace",
        )
    return (mem_min, mem_max)
