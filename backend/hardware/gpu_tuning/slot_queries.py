"""SoAI - GPU slot read operations [backend/hardware/gpu_tuning/slot_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.gpu_control_operation_types import GPUClockCombinationUnsupportedError
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from hardware.control.profiles import default_boot_payload
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_capabilities import get_tuning_capabilities_for_services
from hardware.gpu_tuning.slot_errors import (
    apply_failed_error,
    device_missing_error,
    devices,
    empty_device_entry,
    slot_empty_error,
)
from hardware.gpu_tuning.slot_payload import observe_locked_slot_inventory
from hardware.gpu_tuning.slot_resolution import (
    load_preview_slot_inventory_payload_or_error,
)
from hardware.gpu_tuning.slot_state import build_live_state
from hardware.presets.inventory_snapshot import canonical_gpu_inventory, resolve_inventory_device_id
from hardware.presets.slot_alias_authority import (
    normalize_slot_aliases,
    require_slot_alias_authority,
)
from hardware.presets.slot_alias_profiles import project_alias_history
from hardware.vendors.nvidia.nvml_clock_preparation import (
    require_compatible_nvml_clock_facilities,
    selected_nvml_clock_facilities,
)
from hardware.vendors.vendor_types import NVIDIA_VENDOR

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict

__all__ = (
    "sync_list_gpu_slots",
    "sync_preview_gpu_slot",
)


def _resolve_device_capabilities(
    *,
    capabilities: JSONDict,
    inventory: dict[str, JSONDict],
    device_id: str,
    gpu_services: GpuServiceDependencies,
    nvidia_inventory_available: bool,
) -> JSONDict | None:
    info = inventory.get(device_id)
    if info is None:
        return None
    gpu_index = normalize_gpu_index(info.get("gpu_index"))
    cap_entry = get_capabilities_for_device(capabilities, device_id, gpu_index)
    if cap_entry is None:
        return None
    if (
        cap_entry.get("device_id") != device_id
        or normalize_gpu_index(cap_entry.get("index")) != gpu_index
    ):
        gpu_services.gpu_info_cache_service.invalidate_cache(
            owner="hardware.gpu_slots", reason="capability_identity_mismatch"
        )
        return None
    if not nvidia_inventory_available and cap_entry.get("vendor") == NVIDIA_VENDOR:
        return None
    return cap_entry


def sync_list_gpu_slots(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    device_id: str | None,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    capabilities = get_tuning_capabilities_for_services(
        executor=executor,
        gpu_services=gpu_services,
        logger=logger,
    )
    observation = observe_locked_slot_inventory(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
        allow_create=True,
    )
    inventory = observation.inventory
    nvidia_available = observation.nvidia_inventory_available
    devices_payload = copy.deepcopy(devices(observation.payload))
    if device_id:
        canonical = resolve_inventory_device_id(inventory, device_id)
        if canonical is None:
            return device_missing_error(device_id)
        require_slot_alias_authority(observation.payload, inventory, canonical)
        entry = devices(observation.payload).get(canonical)
        if not isinstance(entry, dict):
            info = inventory.get(canonical, {})
            entry = empty_device_entry(info)
        entry_copy = copy.deepcopy(entry)
        entry_copy["reconciliation"] = project_alias_history(observation.payload, canonical)
        entry_copy["gpu_index"] = inventory[canonical].get("gpu_index")
        cap_entry = _resolve_device_capabilities(
            capabilities=capabilities,
            inventory=inventory,
            device_id=canonical,
            gpu_services=gpu_services,
            nvidia_inventory_available=nvidia_available,
        )
        entry_copy["live"] = build_live_state(canonical, entry_copy, cap_entry)
        return {
            "success": True,
            "version": 1,
            "devices": {device_id: entry_copy},
        }
    response_devices: dict[str, JSONDict] = {}
    conflicts = normalize_slot_aliases(
        copy.deepcopy(observation.payload), inventory
    ).conflicting_device_ids
    for dev_id, info in canonical_gpu_inventory(inventory).items():
        if isinstance((entry := devices_payload.get(dev_id)), dict):
            response_devices[dev_id] = copy.deepcopy(entry)
        else:
            response_devices[dev_id] = empty_device_entry(info)
    for dev_id, entry in devices_payload.items():
        if dev_id not in inventory and isinstance(entry, dict):
            response_devices[dev_id] = copy.deepcopy(entry)
    for dev_id, entry in response_devices.items():
        entry["reconciliation"] = project_alias_history(observation.payload, dev_id)
        current_info = inventory.get(dev_id)
        entry["gpu_index"] = current_info.get("gpu_index") if current_info is not None else None
        cap_entry = _resolve_device_capabilities(
            capabilities=capabilities,
            inventory=inventory,
            device_id=dev_id,
            gpu_services=gpu_services,
            nvidia_inventory_available=nvidia_available,
        )
        entry["live"] = build_live_state(dev_id, entry, cap_entry)
    response: JSONDict = {
        "success": True,
        "version": 1,
        "devices": response_devices,
        "warnings": None,
    }
    if conflicts:
        response["warnings"] = {
            "type": "gpu_slot_alias_conflict",
            "device_ids": sorted(conflicts),
            "message": "Saved GPU aliases contain conflicting or unrecognized state. Review the saved profiles before changing these GPUs.",
        }
    return response


def sync_preview_gpu_slot(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    device_id: str,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    resolved = load_preview_slot_inventory_payload_or_error(
        slot=slot,
        logger=logger,
        executor=executor,
        gpu_services=gpu_services,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
    )
    if isinstance(resolved, dict):
        return resolved
    slot_id, _deps, inventory, payload = resolved
    canonical = resolve_inventory_device_id(inventory, device_id)
    if canonical is None:
        return device_missing_error(device_id)
    require_slot_alias_authority(payload, inventory, canonical)
    entry = devices(payload).get(canonical)
    slots_val = entry.get("slots") if isinstance(entry, dict) else None
    slots_dict = slots_val if isinstance(slots_val, dict) else {}
    slot_entry = slots_dict.get(slot_id)
    if not isinstance(entry, dict) or not isinstance(slot_entry, dict):
        return slot_empty_error(device_id, slot_id)
    settings = slot_entry.get("settings")
    if isinstance(settings, dict) and set(settings).intersection(("core_clock", "mem_clock")):
        capabilities = get_tuning_capabilities_for_services(
            executor=executor, gpu_services=gpu_services, logger=logger
        )
        device_caps = get_capabilities_for_device(
            capabilities, canonical, normalize_gpu_index(inventory[canonical].get("gpu_index"))
        )
        try:
            require_compatible_nvml_clock_facilities(
                selected_nvml_clock_facilities(device_caps or {}, settings)
            )
        except GPUClockCombinationUnsupportedError as exception:
            return apply_failed_error(device_id, slot_id, {"code": str(exception.code)})
    boot = entry.get("boot")
    boot_payload = copy.deepcopy(boot) if isinstance(boot, dict) else default_boot_payload()
    return {
        "success": True,
        "device_id": device_id,
        "slot": slot_id,
        "slot_state": copy.deepcopy(slot_entry),
        "boot": boot_payload,
    }
