"""SoAI - Linux PCI GPU inventory enrichment [backend/hardware/gpu_inventory/linux_merge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_identity_normalization import observed_pci_bdf_conflicts
from core.hardware.gpu_physical_identity import GPUInventoryReadState, GPUPhysicalBindingState
from core.hardware.gpu_physical_observations import (
    read_gpu_pci_observations,
    read_gpu_uuid_observations,
)
from core.logging.trace import get_logger
from hardware.gpu_inventory.display_name import select_gpu_display_name
from hardware.gpu_inventory.linux_physical_acquisition import GPU_CLASS_IDS
from hardware.gpu_inventory.physical_binding import (
    mark_gpu_inventory_bindings,
    match_gpu_inventory_sources,
    retain_gpu_native_aliases,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from hardware.gpu_inventory.linux_physical_acquisition import LinuxPhysicalAcquisition

__all__ = ("merge_linux_gpu_inventory",)

LOGGER_NAME = "SoAI.hardware.gpu_inventory.linux_merge"

BASELINE_IDENTITY_KEYS = (
    "device_id",
    "device_id_aliases",
    "index",
    "name",
    "pci_bdf",
    "pci_bdf_observations",
    "pci_bdf_full",
    "pci_class",
    "pci_class_id",
    "pci_vendor_id",
    "pci_device_id",
    "kernel_driver",
    "kernel_modules",
    "gpu_uuid",
    "gpu_uuid_observations",
    "uuid",
    "native_device_path",
    "platform_driver",
    "platform_compatible",
    "display_adapter_type",
    "pci_function_relationship",
    "primary_pci_bdf_full",
)


def merge_linux_gpu_inventory(
    baseline_gpus: list[JSONDict],
    telemetry_gpus: list[JSONDict],
    *,
    pci_acquisition: LinuxPhysicalAcquisition | None = None,
) -> list[JSONDict]:
    telemetry_gpus = [
        gpu for gpu in telemetry_gpus if not _contradicts_pci_inventory(gpu, pci_acquisition)
    ]
    merged = [copy.deepcopy(gpu) for gpu in baseline_gpus]
    joins = match_gpu_inventory_sources(baseline_gpus, telemetry_gpus)
    matched_native: set[int] = set()
    for baseline_index, native_index in joins.pairs:
        merged[baseline_index] = _merge_gpu_entry(
            merged[baseline_index], telemetry_gpus[native_index]
        )
        matched_native.add(native_index)
    for index, result in enumerate(joins.baseline_results):
        if result.state in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            merged[index]["control_binding_state"] = result.state.value
            merged[index]["control_binding_reason"] = result.reason_code
    for native_index, telemetry_gpu in enumerate(telemetry_gpus):
        if native_index in matched_native:
            continue
        appended = _mark_telemetry_available(telemetry_gpu)
        appended["index"] = len(merged)
        result = joins.native_results[native_index]
        if result.state in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            appended["control_binding_state"] = result.state.value
            appended["control_binding_reason"] = result.reason_code
        merged.append(appended)
    mark_gpu_inventory_bindings(merged)
    return merged


def _contradicts_pci_inventory(
    gpu: JSONDict, pci_acquisition: LinuxPhysicalAcquisition | None
) -> bool:
    if pci_acquisition is None:
        return False
    try:
        observations = read_gpu_pci_observations(gpu)
    except ValidationError:
        return False
    if not observations:
        return False
    candidates = [
        record
        for record in pci_acquisition.records
        if all(not observed_pci_bdf_conflicts(value, record.slot) for value in observations)
    ]
    contradictory = (
        all(
            record.pci_class_id not in GPU_CLASS_IDS
            or (
                record.vendor != "unknown"
                and gpu.get("type") not in (record.vendor, "unknown", None)
            )
            for record in candidates
        )
        if candidates
        else pci_acquisition.state == GPUInventoryReadState.OBSERVED
    )
    if contradictory:
        get_logger(LOGGER_NAME).trace(
            "Native GPU observation contradicts the physical PCI inventory; excluded from GPU roster."
        )
    return contradictory


def _merge_gpu_entry(baseline_gpu: JSONDict, telemetry_gpu: JSONDict) -> JSONDict:
    observations = read_gpu_pci_observations(baseline_gpu)
    observations.extend(
        value for value in read_gpu_pci_observations(telemetry_gpu) if value not in observations
    )
    uuid_observations = read_gpu_uuid_observations(baseline_gpu)
    uuid_observations.extend(
        value
        for value in read_gpu_uuid_observations(telemetry_gpu)
        if value not in uuid_observations
    )
    merged = copy.deepcopy(baseline_gpu)
    baseline_index = baseline_gpu.get("index")
    for key, value in telemetry_gpu.items():
        if key == "compute_capable" and baseline_gpu.get("compute_capable") is False:
            continue
        if key in BASELINE_IDENTITY_KEYS and key in baseline_gpu:
            continue
        merged[key] = copy.deepcopy(value)
    merged["pci_bdf_observations"] = observations
    merged["gpu_uuid_observations"] = uuid_observations
    merged["index"] = baseline_index
    retain_gpu_native_aliases(merged, telemetry_gpu)
    merged["name"] = select_gpu_display_name(baseline_gpu.get("name"), telemetry_gpu.get("name"))
    merged["telemetry_available"] = telemetry_gpu.get("telemetry_available") is not False
    merged["telemetry_unavailable_reason"] = (
        telemetry_gpu.get("telemetry_unavailable_reason")
        if merged["telemetry_available"] is False
        or (
            telemetry_gpu.get("telemetry_available") is True
            and telemetry_gpu.get("telemetry_unavailable_reason") == "process_query_failed"
        )
        else None
    )
    return merged


def _mark_telemetry_available(gpu: JSONDict) -> JSONDict:
    cloned = copy.deepcopy(gpu)
    cloned["telemetry_available"] = gpu.get("telemetry_available") is not False
    cloned["telemetry_unavailable_reason"] = (
        gpu.get("telemetry_unavailable_reason")
        if cloned["telemetry_available"] is False
        or (
            gpu.get("telemetry_available") is True
            and gpu.get("telemetry_unavailable_reason") == "process_query_failed"
        )
        else None
    )
    if "compute_capable" not in cloned:
        cloned["compute_capable"] = True
    if "display_adapter_type" not in cloned:
        cloned["display_adapter_type"] = None
    return cloned
