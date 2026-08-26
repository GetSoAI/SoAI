"""SoAI - Windows GPU inventory collection [backend/hardware/gpu_inventory/windows_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_value
from core.types.json_value import filter_json_dict_list
from core.validation.strings import coerce_optional_trimmed_str
from hardware.gpu_inventory.windows_adapters import (
    WINDOWS_VIDEO_CONTROLLER_QUERY,
    build_windows_gpu_entry,
    classify_windows_display_adapter,
    coerce_windows_gpu_name,
    detect_windows_adapter_vendor,
)
from hardware.vendors.intel.gpu_info import query_intel_gpus
from hardware.vendors.nvidia.query import resolve_query_nvidia_gpus
from hardware.vendors.vendor_types import (
    AMD_VENDOR,
    INTEL_VENDOR,
    NVIDIA_VENDOR,
    UNKNOWN_VENDOR,
)
from hardware.windows_commands import build_windows_powershell_command

if TYPE_CHECKING:
    from core.hardware.protocols import (
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "WindowsGpuInventory",
    "collect_windows_gpu_inventory",
)

LOGGER_NAME = "SoAI.hardware.gpu_inventory.windows_inventory"
OPERATION = "hardware.gpu_inventory.windows_inventory"


@dataclass(frozen=True, slots=True)
class WindowsGpuInventory:
    gpus: list[JSONDict]
    compute_drivers: JSONDict
    display_adapters: list[JSONDict]


def collect_windows_gpu_inventory(
    executor: CommandExecutorProtocol,
    *,
    detailed: bool,
    vendor_hints: set[str],
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> WindowsGpuInventory:
    try:
        result = executor.execute(
            build_windows_powershell_command(WINDOWS_VIDEO_CONTROLLER_QUERY),
            timeout=30,
            shell=False,
            use_sudo=False,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Windows GPU inventory query failed.",
            operation=OPERATION,
            level="warning",
        )
        return WindowsGpuInventory(gpus=[], compute_drivers={}, display_adapters=[])
    if result.return_code != 0 or not result.stdout:
        get_logger(LOGGER_NAME).warning(
            "PowerShell command failed to get GPU info. RC: %s, Error: %s",
            result.return_code,
            result.stderr,
        )
        return WindowsGpuInventory(gpus=[], compute_drivers={}, display_adapters=[])
    try:
        parsed = parse_json_value(result.stdout, field="Win32_VideoController output")
    except ValidationError as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to parse GPU info JSON",
            operation=OPERATION,
        )
        return WindowsGpuInventory(gpus=[], compute_drivers={}, display_adapters=[])
    records = filter_json_dict_list(parsed if isinstance(parsed, list) else [parsed])
    nvidia_gpus, nvidia_drivers = _query_nvidia_details(
        detailed,
        vendor_hints,
        nvidia_nvml_gate,
        nvidia_capabilities_cache_service,
    )
    intel_gpus, intel_drivers = _query_intel_details(executor, detailed, vendor_hints)
    drivers: JSONDict = {}
    drivers.update(nvidia_drivers)
    drivers.update(intel_drivers)
    gpus: list[JSONDict] = []
    display_adapters: list[JSONDict] = []
    vendor_counts: dict[str, int] = {}
    detail_indexes = {NVIDIA_VENDOR: 0, INTEL_VENDOR: 0}
    for record in records:
        name = coerce_windows_gpu_name(record.get("Name"))
        vendor = detect_windows_adapter_vendor(record, name)
        adapter_type = classify_windows_display_adapter(
            gpu_info=record,
            vendor=vendor,
            name=name,
        )
        if adapter_type is not None:
            display_adapters.append(
                build_windows_gpu_entry(
                    gpu_info=record,
                    gpu_index=len(display_adapters),
                    vendor=vendor,
                    vendor_id=len(display_adapters),
                    name=name,
                    compute_capable=False,
                    display_adapter_type=adapter_type,
                ),
            )
            continue
        vendor_id = _next_vendor_id(vendor_counts, vendor)
        gpu_data = build_windows_gpu_entry(
            gpu_info=record,
            gpu_index=len(gpus),
            vendor=vendor,
            vendor_id=vendor_id,
            name=name,
        )
        _apply_driver_version(drivers, vendor, record.get("DriverVersion"))
        if vendor == NVIDIA_VENDOR:
            _merge_vendor_details(gpu_data, nvidia_gpus, detail_indexes, NVIDIA_VENDOR)
        elif vendor == INTEL_VENDOR:
            _merge_vendor_details(gpu_data, intel_gpus, detail_indexes, INTEL_VENDOR)
        gpus.append(gpu_data)
    return WindowsGpuInventory(
        gpus=gpus, compute_drivers=drivers, display_adapters=display_adapters
    )


def _query_nvidia_details(
    detailed: bool,
    vendor_hints: set[str],
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
) -> tuple[list[JSONDict], JSONDict]:
    if NVIDIA_VENDOR not in vendor_hints:
        return ([], {})
    query_nvidia_gpus = resolve_query_nvidia_gpus()
    return query_nvidia_gpus(
        detailed,
        nvml_gate=nvidia_nvml_gate,
        capabilities_cache_service=nvidia_capabilities_cache_service,
    )


def _query_intel_details(
    executor: CommandExecutorProtocol,
    detailed: bool,
    vendor_hints: set[str],
) -> tuple[list[JSONDict], JSONDict]:
    if INTEL_VENDOR not in vendor_hints:
        return ([], {})
    return query_intel_gpus(executor, detailed)


def _next_vendor_id(vendor_counts: dict[str, int], vendor: str) -> int:
    normalized_vendor = (
        vendor if vendor in {NVIDIA_VENDOR, AMD_VENDOR, INTEL_VENDOR} else UNKNOWN_VENDOR
    )
    vendor_id = vendor_counts.get(normalized_vendor, 0)
    vendor_counts[normalized_vendor] = vendor_id + 1
    return vendor_id


def _merge_vendor_details(
    gpu_data: JSONDict,
    details: list[JSONDict],
    detail_indexes: dict[str, int],
    vendor: str,
) -> None:
    detail_index = detail_indexes.get(vendor, 0)
    if detail_index >= len(details):
        return
    detail = details[detail_index]
    for detail_key, detail_value in detail.items():
        if detail_key not in {"type", "vendor_id", "name"}:
            gpu_data[detail_key] = detail_value
    detail_indexes[vendor] = detail_index + 1


def _apply_driver_version(drivers: JSONDict, vendor: str, value: JSONValue) -> None:
    driver_version = coerce_optional_trimmed_str(value)
    if driver_version is None:
        return
    if vendor == UNKNOWN_VENDOR:
        return
    driver_key = f"{vendor.upper()}_Driver"
    if driver_key in drivers:
        return
    drivers[driver_key] = {
        "version": driver_version,
        "driver_version": driver_version,
    }
