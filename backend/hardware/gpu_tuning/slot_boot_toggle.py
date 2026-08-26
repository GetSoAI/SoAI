"""SoAI - GPU slot boot toggle write operations [backend/hardware/gpu_tuning/slot_boot_toggle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from hardware.gpu_tuning.boot_state import (
    boot_payload_from_value,
    disabled_boot_payload,
    slot_toggle_enabled_boot_payload,
)
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.slot_errors import slot_empty_error
from hardware.gpu_tuning.slot_operation_preparation import prepare_slot_boot_toggle_operation

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("sync_toggle_gpu_slot_boot",)


def sync_toggle_gpu_slot_boot(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    device_id: str,
    slot: str | int,
    enabled: JSONValue,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    prepared = prepare_slot_boot_toggle_operation(
        executor=executor,
        storage=storage,
        detailed_gpu_info=detailed_gpu_info,
        device_id=device_id,
        slot=slot,
        enabled=enabled,
        gpu_services=gpu_services,
    )
    if isinstance(prepared, dict):
        return prepared
    slot_id = prepared.slot_id
    flag = prepared.flag
    context = prepared.context
    entry = context.entry
    payload = context.payload
    if not isinstance(entry, dict):
        return slot_empty_error(device_id, slot_id)
    current_boot = boot_payload_from_value(entry.get("boot"))
    if flag:
        slots_value = entry.get("slots")
        slots_dict = slots_value if isinstance(slots_value, dict) else {}
        slot_entry = slots_dict.get(slot_id)
        if not (
            isinstance(slot_entry, dict)
            and isinstance((signature := slot_entry.get("signature")), str)
            and signature
            and isinstance(slot_entry.get("last_applied_at"), str)
            and current_boot.get("applied_signature") == signature
        ):
            return build_gpu_operation_error(
                "slot_requires_apply",
                "Apply the slot with apply_at_boot=true before enabling the boot toggle.",
                device_id=device_id,
                slot=slot_id,
            )
        desired_boot = slot_toggle_enabled_boot_payload(current_boot, slot_id)
    else:
        desired_boot = disabled_boot_payload()
    if current_boot == desired_boot:
        return build_gpu_operation_error(
            "boot_unchanged",
            "Boot preference is already set to the requested state.",
            device_id=device_id,
            slot=slot_id,
        )
    entry["boot"] = desired_boot
    storage.write_payload(payload)
    entry_snapshot = copy.deepcopy(entry)
    return {"success": True, "slot": slot_id, "device_id": device_id, "entry": entry_snapshot}
