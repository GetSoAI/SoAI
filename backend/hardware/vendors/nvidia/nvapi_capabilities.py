"""SoAI - NVIDIA NvAPI capability collection [backend/hardware/vendors/nvidia/nvapi_capabilities.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.protocols import NvmlGateProtocol
from core.logging.trace import get_logger
from core.validation.coercion import coerce_int_from_scalar
from hardware.gpu_capabilities.payloads import (
    build_default_gpu_capabilities,
    read_control_capability_section,
    supported_capability_flag,
    update_control_capability_section,
)

if TYPE_CHECKING:
    from core.hardware.protocols import NvApiGpuProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "collect_nvapi_capabilities",
    "merge_nvapi_capabilities",
)

LOGGER_NAME = "SoAI.hardware.vendors.nvapi_capabilities"
OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES = (
    "hardware.nvidia.metrics.collect_nvapi_capabilities"
)
OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_FAN = (
    "hardware.nvidia.metrics.collect_nvapi_capabilities.fan"
)
OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_OVERCLOCK = (
    "hardware.nvidia.metrics.collect_nvapi_capabilities.overclock"
)
OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_POWER = (
    "hardware.nvidia.metrics.collect_nvapi_capabilities.power"
)
OPERATION_HARDWARE_NVIDIA_METRICS_GET_NVAPI_GPU = "hardware.nvidia.metrics.get_nvapi_gpu"


def _coerce_fan_value(value: JSONValue) -> int | None:
    if isinstance(value, list | tuple) and value:
        first_value = value[0]
        return coerce_int_from_scalar(first_value)
    return coerce_int_from_scalar(value)


def _coerce_supported_flag(value: JSONValue) -> bool:
    return supported_capability_flag(
        value,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.nvidia.metrics.coerce_supported_flag",
        recover_message="Failed to parse supported flag (non-critical).",
    )


def _absolute_clock_current(default_value: JSONValue, offset_value: JSONValue) -> int | None:
    default_clock = coerce_int_from_scalar(default_value)
    offset = coerce_int_from_scalar(offset_value)
    if default_clock is None or offset is None:
        return None
    return default_clock + offset


def _update_nvapi_clock_capability(
    gpu_caps: JSONDict,
    caps_key: str,
    offset_value: JSONValue,
) -> None:
    current = _absolute_clock_current(
        read_control_capability_section(gpu_caps, caps_key).get("default"),
        offset_value,
    )
    if current is None:
        return
    update_control_capability_section(
        gpu_caps,
        caps_key,
        {
            "current": current,
            "offset_based": True,
            "supported": True,
        },
    )


def get_nvapi_gpu(vendor_id: int, *, nvml_gate: NvmlGateProtocol) -> NvApiGpuProtocol | None:
    nvapi_support = nvml_gate.nvapi_support
    if not nvapi_support.ensure_initialized():
        return None
    try:
        return nvapi_support.get_phys_gpu(vendor_id)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            nvml_gate.logger,
            exception,
            message="NvAPI failed to resolve physical GPU handle (non-critical).",
            operation=OPERATION_HARDWARE_NVIDIA_METRICS_GET_NVAPI_GPU,
            details={"vendor_id": vendor_id},
            level="trace",
        )
        return None


def collect_nvapi_capabilities(vendor_id: int, *, nvml_gate: NvmlGateProtocol) -> JSONDict:
    gpu_caps = build_default_gpu_capabilities("NVIDIA GPU")
    if not nvml_gate.nvapi_support.ensure_initialized():
        return gpu_caps
    try:
        nvgpu = get_nvapi_gpu(vendor_id, nvml_gate=nvml_gate)
        if nvgpu is None:
            return gpu_caps
        try:
            gpu_name = nvgpu.name
        except AttributeError:
            gpu_name = "NVIDIA GPU"
        gpu_caps["name"] = gpu_name if isinstance(gpu_name, str) and gpu_name else "NVIDIA GPU"
        try:
            try:
                fan_value = nvgpu.fan
            except AttributeError:
                fan_value = None
            current_fan = _coerce_fan_value(fan_value)
            if current_fan is not None:
                update_control_capability_section(
                    gpu_caps,
                    "fan_speed_percent",
                    {"current": current_fan, "supported": True},
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                nvml_gate.logger,
                exception,
                message="NvAPI fan query failed (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_FAN,
                details={"vendor_id": vendor_id},
                level="trace",
            )
        try:
            try:
                power_value = nvgpu.power_limit
            except AttributeError:
                power_value = None
            power_limit = coerce_int_from_scalar(power_value)
            if power_limit is not None:
                update_control_capability_section(
                    gpu_caps,
                    "power_limit_watts",
                    {"current": power_limit, "supported": True},
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                nvml_gate.logger,
                exception,
                message="NvAPI power query failed (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_POWER,
                details={"vendor_id": vendor_id},
                level="trace",
            )
        try:
            overclock = nvgpu.get_overclock()
            if overclock is not None:
                try:
                    overclock_core = overclock.core
                except AttributeError:
                    overclock_core = 0
                try:
                    overclock_memory = overclock.memory
                except AttributeError:
                    overclock_memory = 0
                _update_nvapi_clock_capability(gpu_caps, "core_clock_mhz", overclock_core)
                _update_nvapi_clock_capability(gpu_caps, "mem_clock_mhz", overclock_memory)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                nvml_gate.logger,
                exception,
                message="NvAPI overclock query failed (non-critical).",
                operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES_OVERCLOCK,
                details={"vendor_id": vendor_id},
                level="trace",
            )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            nvml_gate.logger,
            exception,
            message="NvAPI capability collection failed (non-critical).",
            operation=OPERATION_HARDWARE_NVIDIA_METRICS_COLLECT_NVAPI_CAPABILITIES,
            details={"vendor_id": vendor_id},
            level="trace",
        )
    return gpu_caps


def merge_nvapi_capabilities(gpu_caps: JSONDict, nvapi_caps: JSONDict) -> JSONDict:
    for key in ("fan_speed_percent", "core_clock_mhz", "mem_clock_mhz"):
        gpu_caps_entry = read_control_capability_section(gpu_caps, key)
        nvapi_entry = read_control_capability_section(nvapi_caps, key)
        if (not _coerce_supported_flag(gpu_caps_entry.get("supported"))) and _coerce_supported_flag(
            nvapi_entry.get("supported"),
        ):
            merged = dict(nvapi_entry)
            merged["via_nvapi"] = True
            gpu_caps[key] = merged
    return gpu_caps
