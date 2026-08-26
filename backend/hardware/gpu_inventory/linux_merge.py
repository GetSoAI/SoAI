"""SoAI - Linux PCI GPU inventory enrichment [backend/hardware/gpu_inventory/linux_merge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from hardware.gpu_inventory.display_name import select_gpu_display_name
from hardware.gpu_inventory.identity import normalize_gpu_index, normalize_pci_bdf

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("merge_linux_gpu_inventory",)

BASELINE_IDENTITY_KEYS = (
    "device_id",
    "index",
    "name",
    "pci_bdf",
    "pci_bdf_full",
    "pci_class",
    "pci_class_id",
    "pci_vendor_id",
    "pci_device_id",
    "kernel_driver",
    "kernel_modules",
)


def merge_linux_gpu_inventory(
    baseline_gpus: list[JSONDict],
    telemetry_gpus: list[JSONDict],
) -> list[JSONDict]:
    if not baseline_gpus:
        return [_mark_telemetry_available(gpu) for gpu in telemetry_gpus]
    merged = [copy.deepcopy(gpu) for gpu in baseline_gpus]
    matched_telemetry_indexes: set[int] = set()
    for telemetry_index, telemetry_gpu in enumerate(telemetry_gpus):
        baseline_index = _find_matching_baseline(merged, telemetry_gpu)
        if baseline_index is None:
            continue
        merged[baseline_index] = _merge_gpu_entry(merged[baseline_index], telemetry_gpu)
        matched_telemetry_indexes.add(telemetry_index)
    for telemetry_index, telemetry_gpu in enumerate(telemetry_gpus):
        if telemetry_index in matched_telemetry_indexes:
            continue
        appended = _mark_telemetry_available(telemetry_gpu)
        appended["index"] = len(merged)
        merged.append(appended)
    return merged


def _find_matching_baseline(
    baseline_gpus: list[JSONDict],
    telemetry_gpu: JSONDict,
) -> int | None:
    telemetry_bdf = _entry_bdf(telemetry_gpu)
    if telemetry_bdf:
        for index, baseline_gpu in enumerate(baseline_gpus):
            if telemetry_bdf == _entry_bdf(baseline_gpu):
                return index
    telemetry_vendor = telemetry_gpu.get("type")
    telemetry_vendor_id = normalize_gpu_index(telemetry_gpu.get("vendor_id"))
    if not isinstance(telemetry_vendor, str) or telemetry_vendor_id is None:
        return None
    candidates: list[int] = []
    for index, baseline_gpu in enumerate(baseline_gpus):
        if baseline_gpu.get("type") != telemetry_vendor:
            continue
        if normalize_gpu_index(baseline_gpu.get("vendor_id")) == telemetry_vendor_id:
            candidates.append(index)
    return candidates[0] if len(candidates) == 1 else None


def _merge_gpu_entry(baseline_gpu: JSONDict, telemetry_gpu: JSONDict) -> JSONDict:
    merged = copy.deepcopy(baseline_gpu)
    baseline_index = baseline_gpu.get("index")
    for key, value in telemetry_gpu.items():
        if key in BASELINE_IDENTITY_KEYS:
            continue
        merged[key] = copy.deepcopy(value)
    merged["index"] = baseline_index
    merged["name"] = select_gpu_display_name(baseline_gpu.get("name"), telemetry_gpu.get("name"))
    merged["telemetry_available"] = True
    merged["telemetry_unavailable_reason"] = None
    return merged


def _mark_telemetry_available(gpu: JSONDict) -> JSONDict:
    cloned = copy.deepcopy(gpu)
    cloned["telemetry_available"] = True
    cloned["telemetry_unavailable_reason"] = None
    if "compute_capable" not in cloned:
        cloned["compute_capable"] = True
    if "display_adapter_type" not in cloned:
        cloned["display_adapter_type"] = None
    return cloned


def _entry_bdf(gpu: JSONDict) -> str:
    value = gpu.get("pci_bdf") or gpu.get("pci_bus_id") or gpu.get("bus_id")
    return normalize_pci_bdf(value) if isinstance(value, str) else ""
