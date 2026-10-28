"""SoAI - GPU slot payload loading orchestration [backend/hardware/presets/slot_payload_loading.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.hardware.gpu_control_types import (
    GPUSlotReadResult,
    GPUSlotReadState,
    GPUSlotWriteError,
    GPUSlotWriteFailure,
)
from hardware.presets.inventory_snapshot import snapshot_gpu_inventory
from hardware.presets.slot_alias_authority import (
    GpuSlotAliasReconciliation,
    normalize_slot_aliases,
    require_slot_alias_authority,
)
from hardware.presets.slot_control_state import prune_slots_payload
from hardware.vendors.amd.adl_session import AdlRuntime
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
    "read_gpu_slot_mutation_authority",
    "read_canonical_gpu_slot_candidate",
    "snapshot_inventory_and_load_slots_payload",
)


def read_gpu_slot_mutation_authority(
    storage: GpuSlotStorageManagerProtocol,
) -> GPUSlotReadResult:
    read = storage.read_payload()
    if read.migration_required:
        storage.write_payload(read.payload, expected_read=read)
        return storage.read_payload()
    return read


def read_canonical_gpu_slot_candidate(
    storage: GpuSlotStorageManagerProtocol,
    inventory: dict[str, JSONDict],
    device_id: str,
) -> tuple[GPUSlotReadResult, JSONDict, GpuSlotAliasReconciliation]:
    read = read_gpu_slot_mutation_authority(storage)
    payload = copy.deepcopy(read.payload)
    reconciliation = require_slot_alias_authority(payload, inventory, device_id)
    return read, payload, reconciliation


def load_gpu_slots_payload_unlocked(
    storage: GpuSlotStorageManagerProtocol,
    *,
    inventory: dict[str, JSONDict],
    prune: bool,
    allow_create: bool,
    retained_vendors: frozenset[str] = frozenset(),
) -> JSONDict:
    for attempt in range(3):
        try:
            read = (
                read_gpu_slot_mutation_authority(storage)
                if prune or allow_create
                else storage.read_payload()
            )
            payload = copy.deepcopy(read.payload)
            changed = read.state == GPUSlotReadState.ABSENT and allow_create
            if prune:
                protected = normalize_slot_aliases(payload, inventory).protected_device_ids
                changed = (
                    prune_slots_payload(
                        payload,
                        inventory,
                        retained_vendors=retained_vendors,
                        protected_device_ids=protected,
                    )
                    or changed
                    or payload != read.payload
                )
            if changed:
                storage.write_payload(payload, expected_read=read)
            return payload
        except GPUSlotWriteError as exception:
            if exception.reason != GPUSlotWriteFailure.REVISION_CONFLICT or attempt == 2:
                raise
    raise StateError("GPU slot loading exhausted its bounded revision reconciliation.")


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
    adl_runtime: AdlRuntime | None = None,
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
            adl_runtime=adl_runtime,
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
    adl_runtime: AdlRuntime | None = None,
) -> JSONDict:
    inventory = snapshot_gpu_inventory(
        executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        adl_runtime=adl_runtime,
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
