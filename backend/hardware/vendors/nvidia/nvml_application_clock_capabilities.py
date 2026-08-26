"""SoAI - NVIDIA NVML application clock capabilities [backend/hardware/vendors/nvidia/nvml_application_clock_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Iterable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import (
    read_control_capability_section,
    update_control_capability_section,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = ("apply_application_clock_capabilities",)

APPLICATION_CLOCK_CONTROL_TYPE = "application_clocks"
OPERATION_APPLICATION_CLOCK_CAPABILITIES = "hardware.vendors.nvidia.application_clock_capabilities"

pynvml_module = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


def apply_application_clock_capabilities(
    *,
    handle: ctypes.c_void_p,
    gpu_caps: JSONDict,
    logger: TraceLogger,
) -> None:
    if pynvml_module is None:
        return
    clocks = _read_application_clock_support(handle, logger)
    if clocks is None:
        return
    if not clocks.graphics_clocks:
        return
    _apply_core_application_clock_capability(gpu_caps, clocks)
    if len(clocks.memory_clocks) > 1:
        _apply_memory_application_clock_capability(gpu_caps, clocks)


class _ApplicationClockSupport:
    __slots__ = (
        "current_graphics",
        "current_memory",
        "default_graphics",
        "default_memory",
        "graphics_clocks",
        "memory_clocks",
    )

    def __init__(
        self,
        *,
        current_graphics: int,
        current_memory: int,
        default_graphics: int,
        default_memory: int,
        graphics_clocks: tuple[int, ...],
        memory_clocks: tuple[int, ...],
    ) -> None:
        self.current_graphics = current_graphics
        self.current_memory = current_memory
        self.default_graphics = default_graphics
        self.default_memory = default_memory
        self.graphics_clocks = graphics_clocks
        self.memory_clocks = memory_clocks


def _read_application_clock_support(
    handle: ctypes.c_void_p,
    logger: TraceLogger,
) -> _ApplicationClockSupport | None:
    if pynvml_module is None:
        return None
    try:
        memory_clock_type = pynvml_module.NVML_CLOCK_MEM
        graphics_clock_type = pynvml_module.NVML_CLOCK_GRAPHICS
        memory_clocks = _coerce_clock_values(
            pynvml_module.nvmlDeviceGetSupportedMemoryClocks(handle),
        )
        graphics_clocks = _read_supported_graphics_clocks(handle, memory_clocks)
        current_memory = pynvml_module.nvmlDeviceGetApplicationsClock(
            handle,
            memory_clock_type,
        )
        current_graphics = pynvml_module.nvmlDeviceGetApplicationsClock(
            handle,
            graphics_clock_type,
        )
        default_memory = pynvml_module.nvmlDeviceGetDefaultApplicationsClock(
            handle,
            memory_clock_type,
        )
        default_graphics = pynvml_module.nvmlDeviceGetDefaultApplicationsClock(
            handle,
            graphics_clock_type,
        )
    except pynvml_module.NVMLError as exception:
        _log_application_clock_probe_failure(logger, exception)
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="NVML application-clock capability query failed (non-critical).",
            operation=OPERATION_APPLICATION_CLOCK_CAPABILITIES,
            level="trace",
        )
        return None
    if not memory_clocks or not graphics_clocks:
        return None
    current_memory_value = coerce_int_from_scalar(current_memory)
    current_graphics_value = coerce_int_from_scalar(current_graphics)
    default_memory_value = coerce_int_from_scalar(default_memory)
    default_graphics_value = coerce_int_from_scalar(default_graphics)
    if (
        current_memory_value is None
        or current_graphics_value is None
        or default_memory_value is None
        or default_graphics_value is None
    ):
        return None
    return _ApplicationClockSupport(
        current_graphics=current_graphics_value,
        current_memory=current_memory_value,
        default_graphics=default_graphics_value,
        default_memory=default_memory_value,
        graphics_clocks=graphics_clocks,
        memory_clocks=memory_clocks,
    )


def _read_supported_graphics_clocks(
    handle: ctypes.c_void_p,
    memory_clocks: tuple[int, ...],
) -> tuple[int, ...]:
    if pynvml_module is None:
        return ()
    values: list[int] = []
    for memory_clock in memory_clocks:
        for graphics_clock in _coerce_clock_values(
            pynvml_module.nvmlDeviceGetSupportedGraphicsClocks(handle, memory_clock),
        ):
            if graphics_clock not in values:
                values.append(graphics_clock)
    values.sort()
    return tuple(values)


def _coerce_clock_values(values: Iterable[int]) -> tuple[int, ...]:
    clocks: list[int] = []
    for value in values:
        clock = coerce_int_from_scalar(value)
        if clock is not None and clock not in clocks:
            clocks.append(clock)
    clocks.sort()
    return tuple(clocks)


def _apply_core_application_clock_capability(
    gpu_caps: JSONDict,
    clocks: _ApplicationClockSupport,
) -> None:
    section = read_control_capability_section(gpu_caps, "core_clock_mhz")
    if section.get("supported") is True:
        return
    update_control_capability_section(
        gpu_caps,
        "core_clock_mhz",
        {
            "supported": True,
            "current": clocks.current_graphics,
            "default": clocks.default_graphics,
            "min": min(clocks.graphics_clocks),
            "max": max(clocks.graphics_clocks),
            "via_nvml": True,
            "clock_control_type": APPLICATION_CLOCK_CONTROL_TYPE,
            "allowed_values": list(clocks.graphics_clocks),
            "application_memory_clock_mhz": clocks.current_memory,
            "application_default_memory_clock_mhz": clocks.default_memory,
            "application_supported_memory_clocks_mhz": list(clocks.memory_clocks),
            "application_supported_graphics_clocks_mhz": list(clocks.graphics_clocks),
        },
    )


def _apply_memory_application_clock_capability(
    gpu_caps: JSONDict,
    clocks: _ApplicationClockSupport,
) -> None:
    section = read_control_capability_section(gpu_caps, "mem_clock_mhz")
    if section.get("supported") is True:
        return
    update_control_capability_section(
        gpu_caps,
        "mem_clock_mhz",
        {
            "supported": True,
            "current": clocks.current_memory,
            "default": clocks.default_memory,
            "min": min(clocks.memory_clocks),
            "max": max(clocks.memory_clocks),
            "via_nvml": True,
            "clock_control_type": APPLICATION_CLOCK_CONTROL_TYPE,
            "allowed_values": list(clocks.memory_clocks),
            "application_graphics_clock_mhz": clocks.current_graphics,
            "application_default_graphics_clock_mhz": clocks.default_graphics,
            "application_supported_memory_clocks_mhz": list(clocks.memory_clocks),
            "application_supported_graphics_clocks_mhz": list(clocks.graphics_clocks),
        },
    )


def _log_application_clock_probe_failure(
    logger: TraceLogger,
    exception: Exception,
) -> None:
    log_handled_exception(
        logger,
        exception,
        message="NVML application-clock capability query failed.",
        operation=OPERATION_APPLICATION_CLOCK_CAPABILITIES,
        level="trace",
    )
