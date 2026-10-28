"""SoAI - GPU device field mode storage helpers [backend/hardware/gpu_tuning/device_mode_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING

from hardware.gpu_tuning.slot_capabilities import snapshot_tuning_inventory
from hardware.presets.slot_control_state import update_control_state_for_device
from hardware.presets.slot_payload_loading import read_gpu_slot_mutation_authority

if TYPE_CHECKING:
    from core.hardware.protocols import GpuSlotStorageManagerProtocol
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict
    from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies

__all__ = (
    "DeviceControlStateWriteResult",
    "ensure_device_control_state",
    "ensure_known_device_control_state",
    "load_known_device_slot_state",
)


@dataclass(frozen=True, slots=True)
class DeviceControlStateWriteResult:
    success: bool
    changed: bool
    entry: JSONDict | None


def ensure_device_control_state(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    gpu_services: GpuServiceDependencies,
    device_id: str,
    field_modes: JSONDict,
    applied_settings: JSONDict,
) -> DeviceControlStateWriteResult:
    inventory = snapshot_tuning_inventory(
        executor=executor,
        detailed_gpu_info=detailed_gpu_info,
        gpu_services=gpu_services,
    )
    device_info = inventory.get(device_id)
    if not isinstance(device_info, dict):
        return DeviceControlStateWriteResult(success=False, changed=False, entry=None)
    with storage.lock:
        read = read_gpu_slot_mutation_authority(storage)
        slots_payload = copy.deepcopy(read.payload)
        changed = update_control_state_for_device(
            slots_payload,
            device_id,
            device_info,
            field_modes,
            applied_settings,
        )
        devices_value = slots_payload.get("devices")
        device_entry = devices_value.get(device_id) if isinstance(devices_value, dict) else None
        entry_snapshot = copy.deepcopy(device_entry) if isinstance(device_entry, dict) else None
        if changed:
            storage.write_payload(slots_payload, expected_read=read)
        return DeviceControlStateWriteResult(
            success=True,
            changed=changed,
            entry=entry_snapshot,
        )


def load_known_device_slot_state(
    *,
    storage: GpuSlotStorageManagerProtocol,
    device_id: str,
) -> JSONDict | None:
    with storage.lock:
        slots_payload = storage.read_payload().payload
        payload_devices = slots_payload.get("devices")
        device_entry = payload_devices.get(device_id) if isinstance(payload_devices, dict) else None
        return device_entry if isinstance(device_entry, dict) else None


def ensure_known_device_control_state(
    *,
    storage: GpuSlotStorageManagerProtocol,
    device_id: str,
    device_info: JSONDict,
    field_modes: JSONDict,
    applied_settings: JSONDict,
) -> DeviceControlStateWriteResult:
    with storage.lock:
        read = read_gpu_slot_mutation_authority(storage)
        slots_payload = copy.deepcopy(read.payload)
        changed = update_control_state_for_device(
            slots_payload,
            device_id,
            device_info,
            field_modes,
            applied_settings,
        )
        devices_value = slots_payload.get("devices")
        device_entry = devices_value.get(device_id) if isinstance(devices_value, dict) else None
        entry_snapshot = copy.deepcopy(device_entry) if isinstance(device_entry, dict) else None
        if changed:
            storage.write_payload(slots_payload, expected_read=read)
        return DeviceControlStateWriteResult(
            success=True,
            changed=changed,
            entry=entry_snapshot,
        )
