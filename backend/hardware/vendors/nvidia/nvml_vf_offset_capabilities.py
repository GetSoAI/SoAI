"""SoAI - NVIDIA NVML clock-offset capability collection [backend/hardware/vendors/nvidia/nvml_vf_offset_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.imports.availability import module_available
from hardware.gpu_capabilities.payloads import update_control_capability_section
from hardware.vendors.nvidia.nvml_clock_offset_sanitize import resolve_offset_bounds
from hardware.vendors.nvidia.nvml_metric_reading import is_nvml_error_not_supported
from hardware.vendors.nvidia.nvml_modern_clock_offsets import read_modern_clock_offset

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict

__all__ = ("apply_vf_offset_capabilities",)

OPERATION_APPLY_VF_OFFSET_CAPABILITIES = (
    "hardware.vendors.nvidia.nvml_capabilities.apply_vf_offset_capabilities"
)

pynvml_module = None
if module_available("pynvml"):
    import pynvml

    pynvml_module = pynvml


def apply_vf_offset_capabilities(
    *,
    handle: ctypes.c_void_p,
    gpu_caps: JSONDict,
    logger: TraceLogger,
    default_clock: int | None,
    legacy_min_max_offset_reader: Callable[[ctypes.c_void_p], tuple[int, int]] | None,
    legacy_current_offset_reader: Callable[[ctypes.c_void_p], int] | None,
    modern_clock_type: int | None,
    pstate: int | None,
    caps_key: str,
    operation: str,
) -> None:
    if pynvml_module is None or default_clock is None:
        return
    raw = _resolve_raw_offsets(
        handle=handle,
        logger=logger,
        legacy_min_max_offset_reader=legacy_min_max_offset_reader,
        legacy_current_offset_reader=legacy_current_offset_reader,
        modern_clock_type=modern_clock_type,
        pstate=pstate,
        operation=operation,
    )
    if raw is None:
        return
    current_offset, raw_min, raw_max = raw
    bounds = resolve_offset_bounds(raw_min, raw_max)
    if bounds is None:
        return
    offset_min, offset_max = bounds
    update_control_capability_section(
        gpu_caps,
        caps_key,
        {
            "supported": True,
            "offset_min": offset_min,
            "offset_max": offset_max,
            "current": default_clock + current_offset,
            "min": default_clock + offset_min,
            "max": default_clock + offset_max,
            "via_nvml": True,
        },
    )


def _resolve_raw_offsets(
    *,
    handle: ctypes.c_void_p,
    logger: TraceLogger,
    legacy_min_max_offset_reader: Callable[[ctypes.c_void_p], tuple[int, int]] | None,
    legacy_current_offset_reader: Callable[[ctypes.c_void_p], int] | None,
    modern_clock_type: int | None,
    pstate: int | None,
    operation: str,
) -> tuple[int, int, int] | None:
    if modern_clock_type is not None and pstate is not None:
        modern = read_modern_clock_offset(
            handle=handle,
            clock_type=modern_clock_type,
            pstate=pstate,
            logger=logger,
            operation=operation,
        )
        if modern is not None:
            return modern
    return _resolve_legacy_offsets(
        handle=handle,
        logger=logger,
        min_max_offset_reader=legacy_min_max_offset_reader,
        current_offset_reader=legacy_current_offset_reader,
        operation=operation,
    )


def _resolve_legacy_offsets(
    *,
    handle: ctypes.c_void_p,
    logger: TraceLogger,
    min_max_offset_reader: Callable[[ctypes.c_void_p], tuple[int, int]] | None,
    current_offset_reader: Callable[[ctypes.c_void_p], int] | None,
    operation: str,
) -> tuple[int, int, int] | None:
    if not callable(min_max_offset_reader) or not callable(current_offset_reader):
        return None
    current_offset = _read_legacy_int(handle, current_offset_reader, logger, operation)
    if current_offset is None:
        return None
    offsets = _read_legacy_min_max(handle, min_max_offset_reader, logger, operation)
    if offsets is None:
        return None
    return (current_offset, offsets[0], offsets[1])


def _read_legacy_int(
    handle: ctypes.c_void_p,
    reader: Callable[[ctypes.c_void_p], int],
    logger: TraceLogger,
    operation: str,
) -> int | None:
    if pynvml_module is None:
        return None
    try:
        value = reader(handle)
        return value if isinstance(value, int) else None
    except pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            _log_offset_query_failure(logger, exception, operation)
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="NVML clock-offset capability query failed (non-critical).",
            operation=OPERATION_APPLY_VF_OFFSET_CAPABILITIES,
            details={"nvml_operation": operation},
            level="trace",
        )
        return None


def _read_legacy_min_max(
    handle: ctypes.c_void_p,
    reader: Callable[[ctypes.c_void_p], tuple[int, int]],
    logger: TraceLogger,
    operation: str,
) -> tuple[int, int] | None:
    if pynvml_module is None:
        return None
    try:
        offsets = reader(handle)
    except pynvml_module.NVMLError as exception:
        if not is_nvml_error_not_supported(exception):
            _log_offset_query_failure(logger, exception, operation)
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="NVML clock-offset capability query failed (non-critical).",
            operation=OPERATION_APPLY_VF_OFFSET_CAPABILITIES,
            details={"nvml_operation": operation},
            level="trace",
        )
        return None
    if isinstance(offsets, tuple | list) and len(offsets) == 2:
        first, second = offsets[0], offsets[1]
        if isinstance(first, int) and isinstance(second, int):
            return (first, second)
    return None


def _log_offset_query_failure(
    logger: TraceLogger,
    exception: Exception,
    operation: str,
) -> None:
    log_handled_exception(
        logger,
        exception,
        message="NVML clock-offset capability query failed (non-critical).",
        operation=OPERATION_APPLY_VF_OFFSET_CAPABILITIES,
        details={"nvml_operation": operation},
        level="trace",
    )
