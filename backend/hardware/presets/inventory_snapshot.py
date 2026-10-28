"""SoAI - GPU inventory snapshot for preset slot storage [backend/hardware/presets/inventory_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.protocols import (
    NvidiaCapabilitiesCacheServiceProtocol,
    NvmlGateProtocol,
)
from hardware.gpu_info_resolution import (
    build_gpu_info_service_dependencies,
    get_gpu_info_snapshot,
)
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_inventory.physical_binding import (
    gpu_entry_accepts_device_id,
    resolve_gpu_physical_binding,
)
from hardware.internal_protocols import (
    GPUInfoCacheServiceProtocol,
    GPUVendorDetectionServiceProtocol,
)
from hardware.vendors.amd.adl_session import AdlRuntime

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = ("canonical_gpu_inventory", "resolve_inventory_device_id", "snapshot_gpu_inventory")


def canonical_gpu_inventory(inventory: dict[str, JSONDict]) -> dict[str, JSONDict]:
    return {
        device_id: entry
        for device_id, entry in inventory.items()
        if entry.get("device_id", device_id) == device_id
    }


def resolve_inventory_device_id(inventory: dict[str, JSONDict], device_id: str) -> str | None:
    selected = inventory.get(device_id)
    if selected is None:
        return None
    canonical = selected.get("device_id", device_id)
    if (
        not isinstance(canonical, str)
        or inventory.get(canonical) != selected
        or selected.get("control_binding_state")
        in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT.value,
            GPUPhysicalBindingState.INVALID_RESPONSE.value,
        )
    ):
        raise ValidationError("GPU alias does not resolve to a unique canonical device.")
    return canonical


def snapshot_gpu_inventory(
    executor: CommandExecutorProtocol,
    *,
    detailed_gpu_info: bool,
    gpu_info_cache_service: GPUInfoCacheServiceProtocol,
    gpu_vendor_detection_service: GPUVendorDetectionServiceProtocol,
    nvidia_nvml_gate: NvmlGateProtocol,
    nvidia_capabilities_cache_service: NvidiaCapabilitiesCacheServiceProtocol,
    adl_runtime: AdlRuntime | None = None,
) -> dict[str, JSONDict]:
    gpu_info_services = build_gpu_info_service_dependencies(
        gpu_info_cache_service=gpu_info_cache_service,
        gpu_vendor_detection_service=gpu_vendor_detection_service,
        nvidia_nvml_gate=nvidia_nvml_gate,
        nvidia_capabilities_cache_service=nvidia_capabilities_cache_service,
        adl_runtime=adl_runtime,
    )
    raw_info = get_gpu_info_snapshot(
        executor,
        detailed=detailed_gpu_info,
        deps=gpu_info_services,
    )
    devices: dict[str, JSONDict] = {}
    gpus = raw_info.get("gpus") if isinstance(raw_info, dict) else None
    if not isinstance(gpus, list):
        return devices
    for entry in gpus:
        if not isinstance(entry, dict):
            continue
        device_id, index_value = (entry.get("device_id"), entry.get("index"))
        if not isinstance(device_id, str) or not device_id:
            continue
        gpu_index = normalize_gpu_index(index_value)
        if gpu_index is not None and gpu_index < 0:
            gpu_index = None
        gpu_name = entry.get("name")
        device_info: JSONDict = {
            "device_id": device_id,
            "gpu_index": gpu_index,
            "name": gpu_name if isinstance(gpu_name, str) else str(gpu_name),
        }
        vendor = entry.get("vendor") or entry.get("type")
        if isinstance(vendor, str) and vendor:
            device_info["vendor"] = vendor
        for field in (
            "type",
            "vendor",
            "vendor_id",
            "gpu_uuid",
            "gpu_uuid_observations",
            "uuid",
            "pci_bdf",
            "pci_bdf_observations",
            "pci_bdf_full",
            "windows_pnp_instance_id",
            "pci_bus_id",
            "bus_id",
            "device_id_aliases",
            "control_binding_state",
            "control_binding_reason",
        ):
            if field in entry:
                device_info[field] = copy.deepcopy(entry[field])
        if "control_binding_state" not in device_info:
            binding = resolve_gpu_physical_binding(entry, [entry])
            device_info["control_binding_state"] = binding.state.value
            device_info["control_binding_reason"] = binding.reason_code
        if device_id in devices:
            devices[device_id][
                "control_binding_state"
            ] = GPUPhysicalBindingState.IDENTITY_CONFLICT.value
            devices[device_id]["control_binding_reason"] = "ambiguous_device_id"
            continue
        devices[device_id] = device_info
    canonical_ids = frozenset(devices)
    for entry in tuple(devices.values()):
        aliases = entry.get("device_id_aliases")
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if (
                not isinstance(alias, str)
                or alias in canonical_ids
                or not gpu_entry_accepts_device_id(entry, alias)
            ):
                continue
            if alias in devices:
                if devices[alias].get("device_id") == entry["device_id"]:
                    continue
                devices[alias][
                    "control_binding_state"
                ] = GPUPhysicalBindingState.IDENTITY_CONFLICT.value
                devices[alias]["control_binding_reason"] = "ambiguous_device_alias"
            else:
                devices[alias] = copy.deepcopy(entry)
    return devices
