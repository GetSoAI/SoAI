"""SoAI - NVIDIA NVML clock-offset tuning [backend/hardware/vendors/nvidia/tuning_nvml_clock_offsets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.imports.availability import module_available
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import read_control_capability_section
from hardware.result_messages import append_log_message
from hardware.vendors.nvidia.nvml_clock_offset_operations import (
    reset_clock_offsets,
    set_clock_offset,
)
from hardware.vendors.nvidia.tuning_nvml_application_clocks import (
    apply_nvml_application_clock_settings,
    resolve_application_clock_fields,
)

if TYPE_CHECKING:
    import ctypes

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict, JSONValue

    type NvmlDeviceHandle = ctypes.c_void_p

__all__ = ("apply_nvml_clock_settings",)

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def apply_nvml_clock_settings(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    messages: list[str],
    errors: list[str],
    handle: NvmlDeviceHandle,
    reset_clocks: bool,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
    device_set_gpc_clk_vf_offset: Callable[[NvmlDeviceHandle, int], None] | None,
    device_set_mem_clk_vf_offset: Callable[[NvmlDeviceHandle, int], None] | None,
    modern_core_clock_type: int | None,
    modern_mem_clock_type: int | None,
    modern_pstate: int | None,
    capabilities: JSONDict | None,
) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("VF offset APIs not available for clock setting.")
        return False
    core_uses_application_clocks, mem_uses_application_clocks = resolve_application_clock_fields(
        capabilities
    )
    if reset_clocks:
        changed = False
        if core_uses_application_clocks or mem_uses_application_clocks:
            changed = apply_nvml_application_clock_settings(
                logger,
                vendor_id,
                messages=messages,
                errors=errors,
                handle=handle,
                reset_clocks=True,
                core_clock=None,
                mem_clock=None,
                capabilities=capabilities,
            )
        if not core_uses_application_clocks or not mem_uses_application_clocks:
            changed = (
                reset_clock_offsets(
                    logger,
                    vendor_id,
                    messages=messages,
                    errors=errors,
                    handle=handle,
                    reset_core=not core_uses_application_clocks,
                    reset_mem=not mem_uses_application_clocks,
                    core_setter=device_set_gpc_clk_vf_offset,
                    mem_setter=device_set_mem_clk_vf_offset,
                    modern_core_clock_type=modern_core_clock_type,
                    modern_mem_clock_type=modern_mem_clock_type,
                    modern_pstate=modern_pstate,
                )
                or changed
            )
        return changed
    if core_clock is None and mem_clock is None:
        return False
    changed = False
    application_core_clock = core_clock if core_uses_application_clocks else None
    application_mem_clock = mem_clock if mem_uses_application_clocks else None
    if application_core_clock is not None or application_mem_clock is not None:
        changed = apply_nvml_application_clock_settings(
            logger,
            vendor_id,
            messages=messages,
            errors=errors,
            handle=handle,
            reset_clocks=False,
            core_clock=application_core_clock,
            mem_clock=application_mem_clock,
            capabilities=capabilities,
        )
        if errors:
            return changed
    core_clock = None if core_uses_application_clocks else core_clock
    mem_clock = None if mem_uses_application_clocks else mem_clock
    if core_clock is None and mem_clock is None:
        return changed
    caps = capabilities or {}
    core_caps = read_control_capability_section(caps, "core_clock_mhz")
    mem_caps = read_control_capability_section(caps, "mem_clock_mhz")
    core_default = coerce_int_from_scalar(core_caps.get("default"))
    mem_default = coerce_int_from_scalar(mem_caps.get("default"))
    if (core_clock is not None and core_default is None) or (
        mem_clock is not None and mem_default is None
    ):
        errors.append("Default clocks are unavailable; cannot apply clock offsets.")
        return False
    return (
        _apply_requested_clock_offsets(
            logger,
            vendor_id,
            messages=messages,
            errors=errors,
            handle=handle,
            core_clock=core_clock,
            mem_clock=mem_clock,
            core_default=core_default,
            mem_default=mem_default,
            core_setter=device_set_gpc_clk_vf_offset,
            mem_setter=device_set_mem_clk_vf_offset,
            modern_core_clock_type=modern_core_clock_type,
            modern_mem_clock_type=modern_mem_clock_type,
            modern_pstate=modern_pstate,
        )
        or changed
    )


def _apply_requested_clock_offsets(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    messages: list[str],
    errors: list[str],
    handle: NvmlDeviceHandle,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
    core_default: int | None,
    mem_default: int | None,
    core_setter: Callable[[NvmlDeviceHandle, int], None] | None,
    mem_setter: Callable[[NvmlDeviceHandle, int], None] | None,
    modern_core_clock_type: int | None,
    modern_mem_clock_type: int | None,
    modern_pstate: int | None,
) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("VF offset APIs not available for clock setting.")
        return False
    applied_parts: list[str] = []
    changed = False
    try:
        if core_clock is not None:
            core_offset = _resolve_offset(core_clock, core_default, "Core")
            _require_clock_setter(
                handle,
                core_offset,
                legacy_setter=core_setter,
                modern_clock_type=modern_core_clock_type,
                modern_pstate=modern_pstate,
                label="Core",
            )
            changed = True
            applied_parts.append(f"Core: {core_offset:+d}MHz")
        if mem_clock is not None:
            mem_offset = _resolve_offset(mem_clock, mem_default, "Memory")
            _require_clock_setter(
                handle,
                mem_offset,
                legacy_setter=mem_setter,
                modern_clock_type=modern_mem_clock_type,
                modern_pstate=modern_pstate,
                label="Memory",
            )
            changed = True
            applied_parts.append(f"Memory: {mem_offset:+d}MHz")
        if applied_parts:
            message = f"Clock offsets set to {', '.join(applied_parts)}."
            append_log_message(messages, logger, vendor_id, message)
    except (StateError, ValueError) as exception:
        errors.append(f"Failed to set clocks: {exception}")
    except pynvml_module.NVMLError as exception:
        errors.append(f"Failed to set clock offsets: {exception}")
    return changed


def _resolve_offset(value: JSONValue, default_clock: int | None, label: str) -> int:
    if isinstance(value, str) and value.lower() == "auto":
        return 0
    clock_value = coerce_int_from_scalar(value)
    if clock_value is None:
        raise StateError(f"{label} clock value must be numeric or 'auto'.")
    if default_clock is None:
        raise StateError(f"Default {label.lower()} clock is unavailable.")
    return clock_value - default_clock


def _require_clock_setter(
    handle: NvmlDeviceHandle,
    offset_mhz: int,
    *,
    legacy_setter: Callable[[NvmlDeviceHandle, int], None] | None,
    modern_clock_type: int | None,
    modern_pstate: int | None,
    label: str,
) -> None:
    if set_clock_offset(
        handle,
        offset_mhz,
        legacy_setter=legacy_setter,
        modern_clock_type=modern_clock_type,
        modern_pstate=modern_pstate,
    ):
        return
    raise StateError(f"{label} VF offset API is unavailable.")
