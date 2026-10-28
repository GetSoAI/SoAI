"""SoAI - Windows GPU inventory collection [backend/hardware/gpu_inventory/windows_inventory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ProcessError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    gpu_physical_device_observations,
)
from core.hardware.gpu_physical_observations import (
    read_gpu_pci_observations,
    read_gpu_uuid_observations,
)
from core.logging.trace import get_logger
from core.types.json import JSONDict, JSONValue
from hardware.gpu_inventory.display_name import select_gpu_display_name
from hardware.gpu_inventory.identity import uuid_from_device_id
from hardware.gpu_inventory.memory_metrics import bytes_to_mebibytes
from hardware.gpu_inventory.physical_binding import (
    mark_gpu_inventory_bindings,
    match_gpu_inventory_sources,
    match_gpu_physical_identity,
    resolve_gpu_physical_binding,
    retain_gpu_native_aliases,
)
from hardware.gpu_inventory.windows_adapters import (
    build_windows_gpu_entry,
    classify_windows_display_adapter,
    coerce_windows_gpu_name,
    detect_windows_adapter_vendor,
)
from hardware.gpu_inventory.windows_physical_acquisition import (
    WindowsPhysicalAcquisition,
    read_windows_physical_acquisition,
)
from hardware.vendors.amd.adl_memory import acquire_adl_memory
from hardware.vendors.amd.adl_session import AdlRuntime
from hardware.vendors.intel.gpu_info import query_intel_gpus
from hardware.vendors.nvidia.query import resolve_query_nvidia_gpus
from hardware.vendors.vendor_types import (
    AMD_VENDOR,
    INTEL_VENDOR,
    NVIDIA_VENDOR,
    UNKNOWN_VENDOR,
)

if TYPE_CHECKING:
    from core.hardware.protocols import (
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.system.protocols import CommandExecutorProtocol

LOGGER_NAME = "SoAI.hardware.gpu_inventory.windows_inventory"
OPERATION_HARDWARE_WINDOWS_INVENTORY_NVIDIA = "hardware.windows_inventory.nvidia"


WINDOWS_NATIVE_QUERY_FAILURES: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
    StateError,
    ProcessError,
)

__all__ = (
    "WindowsGpuInventory",
    "collect_windows_gpu_inventory",
)


@dataclass(frozen=True, slots=True)
class WindowsGpuInventory:
    gpus: list[JSONDict]
    compute_drivers: JSONDict
    display_adapters: list[JSONDict]
    acquisition: WindowsPhysicalAcquisition
    source_states: JSONDict = field(default_factory=dict[str, JSONValue])


def collect_windows_gpu_inventory(
    executor: CommandExecutorProtocol,
    *,
    detailed: bool,
    vendor_hints: set[str],
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    adl_runtime: AdlRuntime | None = None,
) -> WindowsGpuInventory:
    acquisition = read_windows_physical_acquisition(executor)
    records = acquisition.records
    source_states: JSONDict = {
        "cim": {"state": acquisition.state.value, "reason_code": acquisition.reason_code},
        "nvidia": {"state": "unknown", "reason_code": "native_observation_missing"},
    }

    def observe_nvidia(status: Literal["complete", "partial", "failed"]) -> None:
        source_states["nvidia"] = {
            "state": (
                "observed"
                if status == "complete"
                else "invalid_response" if status == "partial" else "query_failed"
            ),
            "reason_code": (
                None
                if status == "complete"
                else "native_inventory_incomplete" if status == "partial" else "native_query_failed"
            ),
        }

    try:
        query_nvidia_gpus = resolve_query_nvidia_gpus()
        nvidia_gpus, nvidia_drivers = query_nvidia_gpus(
            detailed,
            nvml_gate=nvidia_nvml_gate,
            capabilities_cache_service=nvidia_capabilities_cache_service,
            on_inventory_observed=observe_nvidia,
        )
    except WINDOWS_NATIVE_QUERY_FAILURES as exception:
        observe_nvidia("failed")
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Independent NVIDIA inventory unavailable.",
            operation=OPERATION_HARDWARE_WINDOWS_INVENTORY_NVIDIA,
            level="warning",
        )
        nvidia_gpus, nvidia_drivers = [], {}
    intel_gpus, intel_drivers = _query_intel_details(executor, detailed, vendor_hints)
    drivers: JSONDict = {}
    drivers.update(nvidia_drivers)
    drivers.update(intel_drivers)
    gpus: list[JSONDict] = []
    display_adapters: list[JSONDict] = []
    vendor_counts: dict[str, int] = {}
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
        gpu_data["telemetry_available"] = False
        gpu_data["telemetry_unavailable_reason"] = "native_identity_unavailable"
        gpus.append(gpu_data)
    native_gpus = nvidia_gpus + intel_gpus
    joins = match_gpu_inventory_sources(gpus, native_gpus)
    matched_native: set[int] = set()
    for baseline_index, native_index in joins.pairs:
        _merge_vendor_details(gpus[baseline_index], native_gpus[native_index])
        matched_native.add(native_index)
    for index, binding in enumerate(joins.baseline_results):
        if binding.state in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            gpus[index]["control_binding_state"] = binding.state.value
            gpus[index]["control_binding_reason"] = binding.reason_code
    for index, native_gpu in enumerate(native_gpus):
        if index in matched_native:
            continue
        entry = copy.deepcopy(native_gpu)
        entry["index"] = len(gpus)
        binding = joins.native_results[index]
        if binding.state in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            entry["control_binding_state"] = binding.state.value
            entry["control_binding_reason"] = binding.reason_code
        gpus.append(entry)
    if any(gpu.get("type") == AMD_VENDOR for gpu in gpus):
        memory = acquire_adl_memory(adl_runtime, executor)
        candidates = [gpu_physical_device_observations(row.device) for row in memory.observations]
        for gpu in gpus:
            if gpu.get("type") != AMD_VENDOR:
                continue
            gpu["memory_total_status"] = "unavailable"
            gpu["telemetry_available"] = False
            gpu["telemetry_unavailable_reason"] = memory.reason_code
            binding = resolve_gpu_physical_binding(gpu, candidates)
            matches = [
                row
                for row in memory.observations
                if binding.device is not None and row.device.device_id == binding.device.device_id
            ]
            memory_row = matches[0] if len(matches) == 1 else None
            if memory_row is None:
                gpu["telemetry_unavailable_reason"] = memory.reason_code or binding.reason_code
            if binding.state == GPUPhysicalBindingState.BOUND and memory_row is not None:
                gpu["telemetry_available"] = memory_row.telemetry is not None
                gpu["telemetry_unavailable_reason"] = memory_row.telemetry_reason_code
                if memory_row.telemetry is not None:
                    gpu.update(memory_row.telemetry)
            if (
                binding.state == GPUPhysicalBindingState.BOUND
                and memory_row is not None
                and memory_row.capacity_bytes is not None
            ):
                gpu["memory_total_mb"] = bytes_to_mebibytes(memory_row.capacity_bytes)
                gpu["memory_total_bytes"] = memory_row.capacity_bytes
                gpu["memory_total_source"] = "adl.ADL2_Adapter_MemoryInfo2_Get"
                gpu["memory_total_unit"] = "bytes"
                gpu["memory_total_reported_value"] = memory_row.capacity_bytes
                gpu.pop("memory_total_unavailable_reason", None)
                gpu["memory_total_status"] = "available"
            else:
                gpu["memory_total_unavailable_reason"] = (
                    memory_row.reason_code if memory_row is not None else memory.reason_code
                ) or binding.reason_code
    mark_gpu_inventory_bindings(gpus)
    return WindowsGpuInventory(
        gpus=gpus,
        compute_drivers=drivers,
        display_adapters=display_adapters,
        acquisition=acquisition,
        source_states=source_states,
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
    detail: JSONDict,
) -> None:
    if match_gpu_physical_identity(gpu_data, detail) != GPUPhysicalBindingState.BOUND:
        raise ValidationError("Windows GPU enrichment requires a proved physical relation.")
    observations = read_gpu_pci_observations(gpu_data)
    observations.extend(
        value for value in read_gpu_pci_observations(detail) if value not in observations
    )
    uuid_observations = read_gpu_uuid_observations(gpu_data)
    uuid_observations.extend(
        value for value in read_gpu_uuid_observations(detail) if value not in uuid_observations
    )
    native_id = detail.get("device_id")
    native_uuid = uuid_from_device_id(native_id) if isinstance(native_id, str) else None
    if native_uuid is not None and any(
        native_uuid.casefold() == observation.casefold() for observation in uuid_observations
    ):
        durable_identity = copy.deepcopy(detail)
        retain_gpu_native_aliases(durable_identity, gpu_data)
        gpu_data["device_id"] = native_id
        gpu_data["device_id_aliases"] = durable_identity.get("device_id_aliases", [])
    else:
        retain_gpu_native_aliases(gpu_data, detail)
    native_capacity_available = detail.get("memory_total_mb") is not None
    for detail_key, detail_value in detail.items():
        if not native_capacity_available and detail_key in {
            "memory_total_mb",
            "memory_total_bytes",
            "memory_total_source",
            "memory_total_unit",
            "memory_total_reported_value",
        }:
            continue
        if detail_key in {"device_id", "index", "type", "name", "device_id_aliases"}:
            continue
        if (
            detail_key
            in {
                "gpu_uuid",
                "gpu_uuid_observations",
                "uuid",
                "pci_bdf_full",
                "pci_bdf_observations",
                "windows_pnp_instance_id",
            }
            and detail_key in gpu_data
        ):
            continue
        gpu_data[detail_key] = copy.deepcopy(detail_value)
    gpu_data["pci_bdf_observations"] = observations
    gpu_data["gpu_uuid_observations"] = uuid_observations
    gpu_data["name"] = select_gpu_display_name(gpu_data.get("name"), detail.get("name"))
    gpu_data["telemetry_available"] = detail.get("telemetry_available") is not False
    gpu_data["telemetry_unavailable_reason"] = detail.get("telemetry_unavailable_reason")
