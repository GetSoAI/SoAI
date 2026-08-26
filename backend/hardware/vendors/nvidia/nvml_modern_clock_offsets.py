"""SoAI - NVIDIA NVML modern clock-offset reader [backend/hardware/vendors/nvidia/nvml_modern_clock_offsets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from hardware.vendors.nvidia.internal_protocols import NvmlErrorValueProtocol
from hardware.vendors.nvidia.nvml_metric_reading import is_nvml_error_not_supported

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = ("read_modern_clock_offset", "set_modern_clock_offset")

OPERATION_READ_MODERN_CLOCK_OFFSET = (
    "hardware.vendors.nvidia.nvml_modern_clock_offsets.read_modern_clock_offset"
)

pynvml_module = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


def _is_expected_modern_absence(exception: Exception) -> bool:
    if is_nvml_error_not_supported(exception):
        return True
    active_pynvml_module = pynvml_module
    if active_pynvml_module is None or not isinstance(exception, NvmlErrorValueProtocol):
        return False
    try:
        function_not_found: int = active_pynvml_module.NVML_ERROR_FUNCTION_NOT_FOUND
    except AttributeError:
        return False
    try:
        exception_value = exception.value
    except AttributeError:
        return False
    return exception_value == function_not_found


def read_modern_clock_offset(
    *,
    handle: ctypes.c_void_p,
    clock_type: int,
    pstate: int,
    logger: TraceLogger,
    operation: str,
) -> tuple[int, int, int] | None:
    active_pynvml_module = pynvml_module
    if active_pynvml_module is None:
        return None
    try:
        get_clock_offsets = active_pynvml_module.nvmlDeviceGetClockOffsets
        clock_offset_struct = active_pynvml_module.c_nvmlClockOffset_t
        clock_offset_version = active_pynvml_module.nvmlClockOffset_v1
    except AttributeError:
        return None
    try:
        info = clock_offset_struct()
        info.version = clock_offset_version
        info.type = clock_type
        info.pstate = pstate
        get_clock_offsets(handle, ctypes.byref(info))
        return (
            int(info.clockOffsetMHz),
            int(info.minClockOffsetMHz),
            int(info.maxClockOffsetMHz),
        )
    except active_pynvml_module.NVMLError as exception:
        if not _is_expected_modern_absence(exception):
            log_handled_exception(
                logger,
                exception,
                message="NVML modern clock-offset query failed (non-critical).",
                operation=OPERATION_READ_MODERN_CLOCK_OFFSET,
                details={"nvml_operation": operation},
                level="trace",
            )
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="NVML modern clock-offset query failed (non-critical).",
            operation=OPERATION_READ_MODERN_CLOCK_OFFSET,
            details={"nvml_operation": operation},
            level="trace",
        )
        return None


def set_modern_clock_offset(
    *,
    handle: ctypes.c_void_p,
    clock_type: int | None,
    pstate: int | None,
    offset_mhz: int,
) -> bool:
    active_pynvml_module = pynvml_module
    if active_pynvml_module is None or clock_type is None or pstate is None:
        return False
    try:
        set_clock_offsets = active_pynvml_module.nvmlDeviceSetClockOffsets
        clock_offset_struct = active_pynvml_module.c_nvmlClockOffset_t
        clock_offset_version = active_pynvml_module.nvmlClockOffset_v1
    except AttributeError:
        return False
    try:
        info = clock_offset_struct()
        info.version = clock_offset_version
        info.type = clock_type
        info.pstate = pstate
        info.clockOffsetMHz = offset_mhz
        set_clock_offsets(handle, ctypes.byref(info))
        return True
    except active_pynvml_module.NVMLError as exception:
        if _is_expected_modern_absence(exception):
            return False
        raise
