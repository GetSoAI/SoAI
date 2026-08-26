"""SoAI - NVIDIA NVML clock-offset mutation operations [backend/hardware/vendors/nvidia/nvml_clock_offset_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.imports.availability import module_available
from hardware.result_messages import append_log_message
from hardware.vendors.nvidia.nvml_modern_clock_offsets import set_modern_clock_offset

if TYPE_CHECKING:
    import ctypes

    from core.logging.protocols import TraceLogger

    type NvmlDeviceHandle = ctypes.c_void_p

__all__ = ("reset_clock_offsets", "set_clock_offset")

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def reset_clock_offsets(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    messages: list[str],
    errors: list[str],
    handle: NvmlDeviceHandle,
    reset_core: bool,
    reset_mem: bool,
    core_setter: Callable[[NvmlDeviceHandle, int], None] | None,
    mem_setter: Callable[[NvmlDeviceHandle, int], None] | None,
    modern_core_clock_type: int | None,
    modern_mem_clock_type: int | None,
    modern_pstate: int | None,
) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("VF offset APIs not available for clock reset.")
        return False
    reset_parts: list[str] = []
    changed = False
    try:
        if reset_core and set_clock_offset(
            handle,
            0,
            legacy_setter=core_setter,
            modern_clock_type=modern_core_clock_type,
            modern_pstate=modern_pstate,
        ):
            changed = True
            reset_parts.append("core")
        if reset_mem and set_clock_offset(
            handle,
            0,
            legacy_setter=mem_setter,
            modern_clock_type=modern_mem_clock_type,
            modern_pstate=modern_pstate,
        ):
            changed = True
            reset_parts.append("memory")
    except pynvml_module.NVMLError as exception:
        errors.append(f"Failed to reset clock offsets: {exception}")
        return changed
    if not reset_parts:
        errors.append("VF offset APIs not available for clock reset.")
        return False
    append_log_message(
        messages,
        logger,
        vendor_id,
        f"Clock offsets reset to 0 ({', '.join(reset_parts)}).",
    )
    return True


def set_clock_offset(
    handle: NvmlDeviceHandle,
    offset_mhz: int,
    *,
    legacy_setter: Callable[[NvmlDeviceHandle, int], None] | None,
    modern_clock_type: int | None,
    modern_pstate: int | None,
) -> bool:
    if set_modern_clock_offset(
        handle=handle,
        clock_type=modern_clock_type,
        pstate=modern_pstate,
        offset_mhz=offset_mhz,
    ):
        return True
    if callable(legacy_setter):
        legacy_setter(handle, offset_mhz)
        return True
    return False
