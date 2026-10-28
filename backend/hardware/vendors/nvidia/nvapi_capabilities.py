"""SoAI - NVIDIA NvAPI capability collection [backend/hardware/vendors/nvidia/nvapi_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalDevice
from core.hardware.gpu_physical_observations import (
    read_gpu_pci_observations,
    read_gpu_physical_identity,
    read_gpu_vendor,
)
from core.hardware.protocols import NvmlGateProtocol
from core.logging.trace import get_logger
from hardware.gpu_capabilities.payloads import (
    CONTROL_CAPABILITY_KEYS,
    build_default_gpu_capabilities,
    read_control_capability_section,
    supported_capability_flag,
    update_control_capability_section,
)
from hardware.gpu_inventory.executable_resolution import acquire_gpu_executable
from hardware.vendors.nvidia.nvapi_clock_controls import (
    query_nvapi_clock_controls,
    read_nvapi_clock_conversion,
    read_nvapi_clock_member,
)
from hardware.vendors.nvidia.nvapi_control_observations import (
    acquire_nvapi_control_binding,
    nvapi_clock_readiness_recheck,
)
from hardware.vendors.nvidia.nvapi_fan_controls import (
    query_nvapi_fan_controls,
    read_nvapi_fan_topology,
)
from hardware.vendors.nvidia.nvapi_function_acquisition import resolve_nvapi_function
from hardware.vendors.nvidia.nvapi_physical_binding import NvApiBoundDevice
from hardware.vendors.nvidia.nvapi_power_controls import (
    query_nvapi_power_controls,
    read_nvapi_power_conversion,
    read_nvapi_power_member,
)

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue
    from hardware.vendors.nvidia.internal_protocols import NvmlControlModuleProtocol
    from hardware.vendors.nvidia.nvapi_native_types import NvApiPstates

OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES = (
    "hardware.nvidia.metrics.collect_nvapi_capabilities"
)
OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_NUMERIC = (
    "hardware.nvidia.metrics.collect_nvapi_capabilities.numeric"
)


__all__ = (
    "LOGGER_NAME",
    "QUERY_FAILURES",
    "collect_nvapi_capabilities",
    "merge_nvapi_capabilities",
)

LOGGER_NAME = "SoAI.hardware.vendors.nvapi_capabilities"
QUERY_FAILURES = (StateError, ValidationError, ctypes.ArgumentError, OSError)


def _coerce_supported_flag(value: JSONValue) -> bool:
    return supported_capability_flag(
        value,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.nvidia.metrics.coerce_supported_flag",
        recover_message="Failed to parse supported flag (non-critical).",
    )


def _set_control_forms(section: JSONDict, *, numeric: bool, automatic: bool) -> None:
    section.update(
        numeric_supported=numeric,
        auto_supported=automatic,
        supported=numeric or automatic,
        requires_admin=True,
        via_nvapi=True,
        control_backend="nvidia_nvapi" if numeric or automatic else None,
        unsupported_reason=None if numeric or automatic else "native_control_unavailable",
    )


def _collect_fan(bound: NvApiBoundDevice, query_interface: Callable[[int], int | None]) -> JSONDict:
    control, status = query_nvapi_fan_controls(bound.handle, query_interface=query_interface)
    fans = read_nvapi_fan_topology(control, status)
    setter = resolve_nvapi_function(
        "NvAPI_GPU_ClientFanCoolersSetControl", query_interface=query_interface
    )
    values = {fan.value for fan in fans}
    modes = {fan.mode for fan in fans}
    minimum, maximum = max(fan.minimum for fan in fans), min(fan.maximum for fan in fans)
    section: JSONDict = {
        "current": next(iter(values)) if len(values) == 1 else None,
        "mode": "auto" if modes == {0} else "manual" if modes == {1} else None,
        "min": minimum if minimum <= maximum else None,
        "max": maximum if minimum <= maximum else None,
    }
    _set_control_forms(
        section, numeric=setter is not None and minimum <= maximum, automatic=setter is not None
    )
    return section


def _collect_power(
    bound: NvApiBoundDevice,
    query_interface: Callable[[int], int | None],
    module: NvmlControlModuleProtocol | None,
) -> JSONDict:
    info, status = query_nvapi_power_controls(bound.handle, query_interface=query_interface)
    power = read_nvapi_power_member(info, status)
    setter = resolve_nvapi_function(
        "NvAPI_GPU_ClientPowerPoliciesSetStatus", query_interface=query_interface
    )
    section: JSONDict = {"native_current_milli_percent": power.value, "mode": "manual"}
    _set_control_forms(section, numeric=False, automatic=setter is not None)
    if power.default != 100000:
        section["numeric_unavailable_reason"] = "native_power_reference_unproved"
        return section
    try:
        default_mw = read_nvapi_power_conversion(module, bound.device)
    except QUERY_FAILURES as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="NvAPI numeric conversion authority is unavailable.",
            operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_NUMERIC,
            level="trace",
        )
        section["numeric_unavailable_reason"] = "native_power_reference_unavailable"
        return section
    denominator = 100_000_000
    minimum = (power.minimum * default_mw + denominator - 1) // denominator
    maximum = power.maximum * default_mw // denominator
    section.update(
        current=power.value * default_mw / denominator,
        default=power.default * default_mw / denominator,
        min=minimum,
        max=maximum,
    )
    _set_control_forms(
        section, numeric=setter is not None and minimum <= maximum, automatic=setter is not None
    )
    return section


def _collect_clock(
    bound: NvApiBoundDevice,
    query_interface: Callable[[int], int | None],
    module: NvmlControlModuleProtocol | None,
    domain: int,
    info: NvApiPstates,
) -> JSONDict:
    clock = read_nvapi_clock_member(info, pstate=0, domain=domain)
    setter = resolve_nvapi_function("NvAPI_GPU_SetPstates20", query_interface=query_interface)
    section: JSONDict = {"native_offset_khz": clock.value, "offset_based": True}
    automatic = setter is not None and clock.minimum <= 0 <= clock.maximum
    _set_control_forms(section, numeric=False, automatic=automatic)
    try:
        baseline = read_nvapi_clock_conversion(module, bound.device, domain)
    except QUERY_FAILURES as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="NvAPI numeric conversion authority is unavailable.",
            operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_NUMERIC,
            level="trace",
        )
        section["numeric_unavailable_reason"] = "native_clock_conversion_unavailable"
        return section
    minimum = max(1, baseline + (clock.minimum + 999) // 1000)
    maximum = baseline + clock.maximum // 1000
    current = baseline + clock.value / 1000
    section.update(
        current=current if current > 0 else None, default=baseline, min=minimum, max=maximum
    )
    _set_control_forms(
        section, numeric=setter is not None and minimum <= maximum, automatic=automatic
    )
    return section


def collect_nvapi_capabilities(
    vendor_id: int,
    *,
    nvml_gate: NvmlGateProtocol,
    executor: CommandExecutorProtocol | None = None,
    selected_gpu: JSONDict | None = None,
    nvml_module: NvmlControlModuleProtocol | None = None,
) -> JSONDict:
    gpu_caps = build_default_gpu_capabilities("NVIDIA GPU")
    for key in CONTROL_CAPABILITY_KEYS:
        section = read_control_capability_section(gpu_caps, key)
        _set_control_forms(section, numeric=False, automatic=False)
        section["unsupported_reason"] = "native_context_unavailable"
        gpu_caps[key] = section
    if executor is None or selected_gpu is None:
        return gpu_caps
    try:
        identity = read_gpu_physical_identity(selected_gpu)
        device_id = selected_gpu.get("device_id")
        if (
            identity is None
            or read_gpu_vendor(selected_gpu) != "nvidia"
            or not isinstance(device_id, str)
            or not device_id.strip()
        ):
            raise StateError(
                "NvAPI capability acquisition requires actual selected physical facts."
            )
        target = GPUPhysicalDevice(
            device_id,
            "nvidia",
            identity,
            None,
            None,
            tuple(read_gpu_pci_observations(selected_gpu)),
        )
        query = nvml_gate.nvapi_support.native_query_interface
        if query is None:
            raise StateError("NvAPI native facilities are unavailable.")
        executable = acquire_gpu_executable("nvidia-smi")
        bound = acquire_nvapi_control_binding(
            executor, target=target, executable=executable, query_interface=query
        )
    except QUERY_FAILURES as exception:
        for key in CONTROL_CAPABILITY_KEYS:
            update_control_capability_section(
                gpu_caps, key, {"unsupported_reason": "native_query_unavailable"}
            )
        log_handled_exception(
            nvml_gate.logger,
            exception,
            message="NvAPI physical capability query failed.",
            operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES,
            details={"vendor_id": vendor_id},
            level="trace",
        )
        return gpu_caps
    name = selected_gpu.get("name")
    if isinstance(name, str) and name.strip():
        gpu_caps["name"] = name
    collectors: tuple[tuple[str, Callable[[], JSONDict]], ...] = (
        ("fan_speed_percent", lambda: _collect_fan(bound, query)),
        ("power_limit_watts", lambda: _collect_power(bound, query, nvml_module)),
    )
    for key, collect in collectors:
        try:
            update_control_capability_section(gpu_caps, key, collect())
        except QUERY_FAILURES as exception:
            _record_field_failure(gpu_caps, key, nvml_gate, exception)
    try:
        clock_info = query_nvapi_clock_controls(
            bound.handle,
            query_interface=query,
            readiness_recheck=nvapi_clock_readiness_recheck(
                executor, bound, executable=executable, query_interface=query
            ),
        )
    except QUERY_FAILURES as exception:
        for key in ("core_clock_mhz", "mem_clock_mhz"):
            _record_field_failure(gpu_caps, key, nvml_gate, exception)
    else:
        for key, domain in (("core_clock_mhz", 0), ("mem_clock_mhz", 4)):
            try:
                update_control_capability_section(
                    gpu_caps, key, _collect_clock(bound, query, nvml_module, domain, clock_info)
                )
            except QUERY_FAILURES as exception:
                _record_field_failure(gpu_caps, key, nvml_gate, exception)
    return gpu_caps


def _record_field_failure(
    gpu_caps: JSONDict, key: str, gate: NvmlGateProtocol, exception: Exception
) -> None:
    update_control_capability_section(
        gpu_caps, key, {"unsupported_reason": "native_query_unavailable"}
    )
    log_handled_exception(
        gate.logger,
        exception,
        message="NvAPI field capability query failed.",
        operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES,
        details={"field": key},
        level="trace",
    )


def merge_nvapi_capabilities(gpu_caps: JSONDict, nvapi_caps: JSONDict) -> JSONDict:
    for key in CONTROL_CAPABILITY_KEYS:
        existing = read_control_capability_section(gpu_caps, key)
        candidate = read_control_capability_section(nvapi_caps, key)
        if _coerce_supported_flag(existing.get("supported")):
            continue
        if _coerce_supported_flag(candidate.get("supported")):
            candidate["via_nvapi"] = True
            gpu_caps[key] = candidate
        else:
            for field in ("current", "native_offset_khz", "native_current_milli_percent"):
                if candidate.get(field) is not None:
                    existing[field] = candidate[field]
            for field in (
                "numeric_supported",
                "auto_supported",
                "requires_admin",
                "unsupported_reason",
            ):
                if field in candidate:
                    existing[field] = candidate[field]
            gpu_caps[key] = existing
    return gpu_caps
