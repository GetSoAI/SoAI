"""SoAI - Linux PCI GPU inventory reader [backend/hardware/gpu_inventory/linux_pci.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.timing.epoch import epoch_ms
from hardware.gpu_inventory.display_adapters import classify_display_adapter
from hardware.gpu_inventory.entries import build_gpu_entry
from hardware.gpu_inventory.linux_physical_acquisition import (
    GPU_CLASS_IDS,
    LinuxPciGpuRecord,
    LinuxPhysicalAcquisition,
    read_linux_physical_acquisition,
)
from hardware.gpu_inventory.memory_metrics import bytes_to_mebibytes
from hardware.gpu_inventory.pci_function_relationships import read_pci_function_relationship
from hardware.operations import create_device_id
from hardware.vendors.amd.sysfs_telemetry import read_amd_sysfs_telemetry
from hardware.vendors.intel.i915_frequency import read_i915_telemetry
from hardware.vendors.vendor_types import NVIDIA_VENDOR, UNKNOWN_VENDOR

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("LinuxGpuInventory", "read_linux_pci_gpu_inventory")


@dataclass(frozen=True, slots=True)
class LinuxGpuInventory:
    gpus: list[JSONDict]
    display_adapters: list[JSONDict]
    acquisition: LinuxPhysicalAcquisition


def read_linux_pci_gpu_inventory(
    executor: CommandExecutorProtocol, *, drm_pci_slots: tuple[str, ...] = ()
) -> LinuxGpuInventory:
    acquisition = read_linux_physical_acquisition(executor)
    gpu_records = sorted(
        (record for record in acquisition.records if record.pci_class_id in GPU_CLASS_IDS),
        key=lambda record: record.slot,
    )
    gpus, display_adapters = _partition_gpu_records(gpu_records, drm_pci_slots, executor)
    return LinuxGpuInventory(gpus, display_adapters, acquisition)


def _partition_gpu_records(
    gpu_records: list[LinuxPciGpuRecord],
    drm_pci_slots: tuple[str, ...],
    executor: CommandExecutorProtocol,
) -> tuple[list[JSONDict], list[JSONDict]]:
    vendor_counts: dict[str, int] = {}
    gpus: list[JSONDict] = []
    display_adapters: list[JSONDict] = []
    for record in gpu_records:
        relationship = read_pci_function_relationship(record, gpu_records, drm_pci_slots)
        adapter_type = classify_display_adapter(
            record.vendor,
            record.pci_vendor_id,
            record.kernel_driver,
        )
        if relationship.state == "secondary":
            adapter_type = "secondary_pci_function"
        if adapter_type is not None:
            adapter = _build_pci_entry(
                record,
                index=len(display_adapters),
                vendor_id=len(display_adapters),
                compute_capable=False,
                display_adapter_type=adapter_type,
                executor=executor,
            )
            adapter["pci_function_relationship"] = relationship.state
            adapter["primary_pci_bdf_full"] = relationship.primary_slot
            display_adapters.append(adapter)
            continue
        vendor_id = vendor_counts.get(record.vendor, 0)
        vendor_counts[record.vendor] = vendor_id + 1
        gpu = _build_pci_entry(
            record,
            index=len(gpus),
            vendor_id=vendor_id,
            compute_capable=True,
            display_adapter_type=None,
            executor=executor,
        )
        gpu["pci_function_relationship"] = relationship.state
        gpu["primary_pci_bdf_full"] = relationship.primary_slot
        gpus.append(gpu)
    return gpus, display_adapters


def _build_pci_entry(
    record: LinuxPciGpuRecord,
    *,
    index: int,
    vendor_id: int,
    compute_capable: bool,
    display_adapter_type: str | None,
    executor: CommandExecutorProtocol,
) -> JSONDict:
    gpu_entry = build_gpu_entry(
        vendor=record.vendor,
        index=index,
        vendor_id=vendor_id,
        device_id=create_device_id("gpu", f"{record.vendor}-pci-{record.pci_bdf}"),
        name=_build_display_name(record),
        memory_used_mb=None,
        memory_total_mb=None,
        percent_used=None,
        processes=[],
    )
    gpu_entry.update(
        {
            "compute_capable": compute_capable,
            "display_adapter_type": display_adapter_type,
            "telemetry_available": False,
            "telemetry_unavailable_reason": _telemetry_unavailable_reason(record),
            "pci_bdf": record.pci_bdf,
            "pci_bdf_full": record.slot,
            "pci_class": record.pci_class,
            "pci_class_id": record.pci_class_id,
            "pci_vendor_id": record.pci_vendor_id,
            "pci_device_id": record.pci_device_id,
            "kernel_driver": record.kernel_driver,
            "platform_driver": record.kernel_driver,
            "kernel_modules": list(record.kernel_modules),
        },
    )
    if compute_capable:
        _read_legacy_metrics(gpu_entry, record, executor)
    return gpu_entry


def _telemetry_unavailable_reason(record: LinuxPciGpuRecord) -> str:
    if record.vendor == NVIDIA_VENDOR and (record.kernel_driver or "").lower() != "nvidia":
        return "driver_inactive"
    return "tool_missing"


def _build_display_name(record: LinuxPciGpuRecord) -> str:
    if record.vendor == UNKNOWN_VENDOR:
        return record.device_name or "GPU"
    if record.device_name:
        return record.device_name
    return f"{record.vendor_name} GPU".strip()


def _read_legacy_metrics(
    gpu: JSONDict, record: LinuxPciGpuRecord, executor: CommandExecutorProtocol
) -> None:
    try:
        if record.vendor == "amd" and record.kernel_driver in ("radeon", "amdgpu"):
            metrics = read_amd_sysfs_telemetry(record.slot, executor)
            if metrics is None:
                return
            gpu.update(metrics)
            gpu["temperature"] = metrics.get("temperature_celsius")
            gpu["utilization"] = metrics.get("core_utilization_percent")
            capacity = metrics.get("memory_total_bytes")
            if isinstance(capacity, int) and capacity > 0:
                gpu["memory_total_mb"] = bytes_to_mebibytes(capacity)
                gpu["memory_total_status"] = "available"
                gpu["memory_total_source"] = (
                    metrics.get("memory_total_source") or "drm.sysfs.mem_info_vram_total"
                )
        elif record.vendor == "intel" and record.kernel_driver == "i915":
            gpu.update(read_i915_telemetry(record.slot, executor))
        else:
            return
    except FileNotFoundError:
        return
    except PermissionError:
        gpu["telemetry_unavailable_reason"] = "permission_denied"
        return
    except (StateError, ValidationError):
        gpu["telemetry_unavailable_reason"] = "native_observation_invalid"
        return
    gpu["telemetry_available"] = any(
        gpu.get(field) is not None
        for field in ("temperature", "core_clock_mhz", "utilization", "power_draw_watts")
    )
    if gpu["telemetry_available"]:
        gpu["telemetry_unavailable_reason"] = None
        gpu["telemetry_observed_at_ms"] = epoch_ms()
