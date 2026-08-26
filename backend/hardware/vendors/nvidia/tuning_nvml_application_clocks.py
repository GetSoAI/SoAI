"""SoAI - NVIDIA NVML application clock tuning [backend/hardware/vendors/nvidia/tuning_nvml_application_clocks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.imports.availability import module_available
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import read_control_capability_section
from hardware.result_messages import append_log_message
from hardware.vendors.nvidia.nvml_application_clock_capabilities import (
    APPLICATION_CLOCK_CONTROL_TYPE,
)

if TYPE_CHECKING:
    import ctypes

    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict, JSONValue

    type NvmlDeviceHandle = ctypes.c_void_p

__all__ = (
    "apply_nvml_application_clock_settings",
    "resolve_application_clock_fields",
)

pynvml_module_ref = None
if module_available("pynvml"):
    import pynvml

    pynvml_module_ref = pynvml


def resolve_application_clock_fields(capabilities: JSONDict | None) -> tuple[bool, bool]:
    caps = capabilities or {}
    core_caps = read_control_capability_section(caps, "core_clock_mhz")
    mem_caps = read_control_capability_section(caps, "mem_clock_mhz")
    return (
        core_caps.get("clock_control_type") == APPLICATION_CLOCK_CONTROL_TYPE,
        mem_caps.get("clock_control_type") == APPLICATION_CLOCK_CONTROL_TYPE,
    )


def apply_nvml_application_clock_settings(
    logger: TraceLogger | None,
    vendor_id: int,
    *,
    messages: list[str],
    errors: list[str],
    handle: NvmlDeviceHandle,
    reset_clocks: bool,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
    capabilities: JSONDict | None,
) -> bool:
    pynvml_module = pynvml_module_ref
    if pynvml_module is None:
        errors.append("Application clock APIs are unavailable.")
        return False
    try:
        if reset_clocks:
            pynvml_module.nvmlDeviceResetApplicationsClocks(handle)
            append_log_message(messages, logger, vendor_id, "Application clocks reset.")
            return True
        if core_clock is None and mem_clock is None:
            return False
        target = _resolve_application_clock_target(
            core_clock=core_clock,
            mem_clock=mem_clock,
            capabilities=capabilities,
        )
        pynvml_module.nvmlDeviceSetApplicationsClocks(
            handle,
            target.memory_clock_mhz,
            target.graphics_clock_mhz,
        )
        append_log_message(
            messages,
            logger,
            vendor_id,
            (
                "Application clocks set to "
                f"Memory: {target.memory_clock_mhz}MHz, Core: {target.graphics_clock_mhz}MHz."
            ),
        )
        return True
    except (StateError, ValueError) as exception:
        errors.append(f"Failed to set application clocks: {exception}")
    except pynvml_module.NVMLError as exception:
        errors.append(f"Failed to set application clocks: {exception}")
    return False


class _ApplicationClockTarget:
    __slots__ = ("graphics_clock_mhz", "memory_clock_mhz")

    def __init__(self, *, graphics_clock_mhz: int, memory_clock_mhz: int) -> None:
        self.graphics_clock_mhz = graphics_clock_mhz
        self.memory_clock_mhz = memory_clock_mhz


def _resolve_application_clock_target(
    *,
    core_clock: JSONValue | None,
    mem_clock: JSONValue | None,
    capabilities: JSONDict | None,
) -> _ApplicationClockTarget:
    caps = capabilities or {}
    core_caps = read_control_capability_section(caps, "core_clock_mhz")
    mem_caps = read_control_capability_section(caps, "mem_clock_mhz")
    graphics_clock = _resolve_graphics_clock(core_clock, core_caps, mem_caps)
    memory_clock = _resolve_memory_clock(mem_clock, core_caps, mem_caps)
    return _ApplicationClockTarget(
        graphics_clock_mhz=graphics_clock,
        memory_clock_mhz=memory_clock,
    )


def _resolve_graphics_clock(
    requested_clock: JSONValue | None,
    core_caps: JSONDict,
    mem_caps: JSONDict,
) -> int:
    if requested_clock is not None:
        return _resolve_requested_clock(
            requested_clock,
            caps=core_caps,
            label="Core clock",
        )
    current = coerce_int_from_scalar(mem_caps.get("application_graphics_clock_mhz"))
    if current is not None:
        return current
    current = coerce_int_from_scalar(core_caps.get("current"))
    if current is not None:
        return current
    default = coerce_int_from_scalar(core_caps.get("default"))
    if default is not None:
        return default
    raise StateError("Application core clock is unavailable.")


def _resolve_memory_clock(
    requested_clock: JSONValue | None,
    core_caps: JSONDict,
    mem_caps: JSONDict,
) -> int:
    if requested_clock is not None:
        return _resolve_requested_clock(
            requested_clock,
            caps=mem_caps,
            label="Memory clock",
        )
    current = coerce_int_from_scalar(core_caps.get("application_memory_clock_mhz"))
    if current is not None:
        return current
    current = coerce_int_from_scalar(mem_caps.get("current"))
    if current is not None:
        return current
    default = coerce_int_from_scalar(core_caps.get("application_default_memory_clock_mhz"))
    if default is not None:
        return default
    default = coerce_int_from_scalar(mem_caps.get("default"))
    if default is not None:
        return default
    raise StateError("Application memory clock is unavailable.")


def _resolve_requested_clock(
    requested_clock: JSONValue,
    *,
    caps: JSONDict,
    label: str,
) -> int:
    if isinstance(requested_clock, str) and requested_clock.lower() == "auto":
        default_clock = coerce_int_from_scalar(caps.get("default"))
        if default_clock is None:
            raise StateError(f"Default {label.lower()} is unavailable.")
        return default_clock
    value = coerce_int_from_scalar(requested_clock)
    if value is None:
        raise StateError(f"{label} must be numeric or 'auto'.")
    return value
