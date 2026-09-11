"""SoAI - GPU slot payload loading orchestration [backend/hardware/presets/slot_payload_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.presets.inventory_snapshot import snapshot_gpu_inventory
from hardware.presets.slot_storage import prune_slots_payload
from hardware.vendors.vendor_types import unobserved_vendors

if TYPE_CHECKING:
    from core.hardware.protocols import (
        GpuSlotStorageManagerProtocol,
        NvidiaCapabilitiesCacheServiceProtocol,
        NvmlGateProtocol,
    )
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.internal_protocols import (
        GPUInfoCacheServiceProtocol,
        GPUVendorDetectionServiceProtocol,
    )

__all__ = (
    "load_gpu_slots_payload",
    "load_gpu_slots_payload_unlocked",
    "snapshot_inventory_and_load_slots_payload",
)


def load_gpu_slots_payload_unlocked(
    storage: GpuSlotStorageManagerProtocol,
    *,
    inventory: dict[str, JSONDict],
    prune: bool,
    allow_create: bool,
    retained_vendors: frozenset[str] = frozenset(),
) -> JSONDict:
    payload, existed = storage.read_payload()
    changed = False
    if not existed and allow_create:
        changed = True
    if prune and prune_slots_payload(payload, inventory, retained_vendors=retained_vendors):
        changed = True
    if changed:
        storage.write_payload(payload)
    return payload


def snapshot_inventory_and_load_slots_payload(
    storage: GpuSlotStorageManagerProtocol,
    executor: CommandExecutorProtocol,
    *,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    nvidia_inventory_available: bool,
    prune: bool,
    allow_create: bool,
    inventory: dict[str, JSONDict] | None = None,
) -> tuple[dict[str, JSONDict], JSONDict]:
    inventory_snapshot = inventory
    if inventory_snapshot is None:
        inventory_snapshot = snapshot_gpu_inventory(
            executor,
            detailed_gpu_info=detailed_gpu_info,
            gpu_info_cache_service=gpu_info_cache_service,
            gpu_vendor_detection_service=gpu_vendor_detection_service,
            nvidia_nvml_gate=nvidia_nvml_gate,
            nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        )
    with storage.lock:
        payload = load_gpu_slots_payload_unlocked(
            storage,
            inventory=inventory_snapshot,
            prune=prune,
            allow_create=allow_create,
            retained_vendors=unobserved_vendors(
                nvidia_inventory_available=nvidia_inventory_available,
            ),
        )
    return inventory_snapshot, payload


def load_gpu_slots_payload(
    storage: GpuSlotStorageManagerProtocol,
    executor: CommandExecutorProtocol,
    *,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    prune: bool = True,
    allow_create: bool = True,
) -> JSONDict:
    inventory = snapshot_gpu_inventory(
        executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
    )
    with storage.lock:
        return load_gpu_slots_payload_unlocked(
            storage,
            inventory=inventory,
            prune=prune,
            allow_create=allow_create,
            retained_vendors=unobserved_vendors(
                nvidia_inventory_available=nvidia_capabilities_cache_service.inventory_available()
            ),
        )
