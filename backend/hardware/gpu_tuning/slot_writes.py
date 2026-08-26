"""SoAI - GPU slot settings write operations [backend/hardware/gpu_tuning/slot_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_operation_results import build_gpu_operation_error
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import TraceLogger
from hardware.control.profiles import compute_slot_signature
from hardware.gpu_capabilities.aggregate_payloads import get_capabilities_for_device
from hardware.gpu_inventory.identity import normalize_gpu_index
from hardware.gpu_tuning.apply_at_boot_flag import parse_apply_at_boot_flag_or_error
from hardware.gpu_tuning.boot_state import (
    boot_payload_from_value,
    disabled_boot_payload,
    enabled_boot_payload,
)
from hardware.gpu_tuning.effective_control_state import build_apply_settings_for_modes
from hardware.gpu_tuning.service_dependencies import GpuServiceDependencies
from hardware.gpu_tuning.setting_modes import (
    field_modes_mapping_or_none,
    normalize_field_modes_for_settings,
)
from hardware.gpu_tuning.slot_errors import (
    device_missing_error,
    devices,
    empty_device_entry,
    resolve_slot_identifier_or_error,
    slot_empty_error,
    slot_unchanged_error,
    try_remove_slots_file,
)
from hardware.gpu_tuning.slot_payload import SlotPayloadDependencies
from hardware.gpu_tuning.slot_resolution import (
    load_slot_capabilities_inventory_payload_or_error,
    load_slot_inventory_payload_or_error,
)
from hardware.presets.slot_mutations import store_slot_unlocked
from hardware.presets.slot_storage import ensure_device_entry
from hardware.validate import sanitize_settings

if TYPE_CHECKING:
    from core.system.protocols import CommandExecutorProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "sync_clear_gpu_slot",
    "sync_store_gpu_slot",
)


def sync_store_gpu_slot(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    device_id: str,
    slot: str | int,
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None,
    apply_at_boot: bool | None,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    slot_id_or_error = resolve_slot_identifier_or_error(slot)
    if isinstance(slot_id_or_error, dict):
        return slot_id_or_error
    slot_id = slot_id_or_error
    if not settings:
        return build_gpu_operation_error(
            "invalid_payload",
            "GPU slot settings payload must be a non-empty object.",
            device_id=device_id,
            slot=slot_id,
        )
    settings_payload: JSONDict = dict(settings)
    with storage.lock:
        resolved = load_slot_capabilities_inventory_payload_or_error(
            executor=executor,
            storage=storage,
            detailed_gpu_info=detailed_gpu_info,
            logger=logger,
            slot=slot_id,
            gpu_services=gpu_services,
            allow_create=True,
        )
        if isinstance(resolved, dict):
            return resolved
        resolved_payload: tuple[
            str,
            SlotPayloadDependencies,
            JSONDict,
            dict[str, JSONDict],
            JSONDict,
        ] = resolved
        slot_id, _deps, capabilities, inventory, payload = resolved_payload
        device_info_value = inventory.get(device_id)
        device_info = device_info_value if isinstance(device_info_value, dict) else None
        if not device_info:
            return device_missing_error(device_id)
        entry = ensure_device_entry(payload, device_id, device_info)
        cap_entry = get_capabilities_for_device(
            capabilities,
            device_id,
            normalize_gpu_index(entry.get("gpu_index")),
        )
        try:
            sanitized = sanitize_settings(settings_payload, cap_entry)
        except ValidationError as exception:
            return build_gpu_operation_error(
                "invalid_request_error",
                str(exception),
                device_id=device_id,
                slot=slot_id,
            )
        slot_field_modes = normalize_field_modes_for_settings(sanitized, field_modes)
        try:
            build_apply_settings_for_modes(sanitized, slot_field_modes)
        except ValidationError as exception:
            return build_gpu_operation_error(
                "invalid_request_error",
                str(exception),
                device_id=device_id,
                slot=slot_id,
            )
        slots_value = entry.get("slots")
        slots_dict = slots_value if isinstance(slots_value, dict) else {}
        previous_slot = slots_dict.get(slot_id)
        previous_signature = (
            previous_slot.get("signature") if isinstance(previous_slot, dict) else None
        )
        previous_field_modes = (
            field_modes_mapping_or_none(previous_slot.get("field_modes"))
            if isinstance(previous_slot, dict)
            else None
        )
        new_signature = compute_slot_signature(sanitized, slot_field_modes)
        slot_changed = not (
            isinstance(previous_slot, dict)
            and previous_slot.get("settings") == sanitized
            and previous_field_modes == slot_field_modes
            and (previous_signature == new_signature)
        )
        boot_changed = False
        apply_flag, apply_error = parse_apply_at_boot_flag_or_error(
            device_id=device_id,
            slot_id=slot_id,
            apply_at_boot=apply_at_boot,
            default=None,
        )
        if apply_error is not None:
            return apply_error
        if slot_changed:
            store_slot_unlocked(
                storage,
                payload,
                device_id,
                slot_id,
                sanitized,
                slot_field_modes,
                saved_at=None,
            )
            refreshed_entry = devices(payload).get(device_id)
            if isinstance(refreshed_entry, dict):
                entry = refreshed_entry
        if apply_flag is not None:
            current_boot = boot_payload_from_value(entry.get("boot"))
            desired_boot = (
                enabled_boot_payload(
                    slot_id=slot_id,
                    applied_signature=(
                        current_boot.get("applied_signature")
                        if current_boot.get("slot") == slot_id
                        else None
                    ),
                    applied_at=(
                        current_boot.get("applied_at")
                        if current_boot.get("slot") == slot_id
                        else None
                    ),
                )
                if apply_flag
                else disabled_boot_payload()
            )
            if current_boot != desired_boot:
                entry["boot"], boot_changed = (desired_boot, True)
        if not slot_changed and (not boot_changed):
            return slot_unchanged_error(device_id, slot_id)
        storage.write_payload(payload)
        entry_snapshot = copy.deepcopy(entry)
    return {
        "success": True,
        "device_id": device_id,
        "slot": slot_id,
        "entry": entry_snapshot,
        "boot_changed": boot_changed,
        "signature": new_signature if slot_changed else previous_signature,
    }


def sync_clear_gpu_slot(
    *,
    executor: CommandExecutorProtocol,
    storage: GpuSlotStorageManagerProtocol,
    gpu_slots_path: str,
    detailed_gpu_info: bool,
    logger: TraceLogger,
    device_id: str,
    slot: str | int,
    gpu_services: GpuServiceDependencies,
) -> JSONDict:
    with storage.lock:
        allow_slot_creation = False
        resolved = load_slot_inventory_payload_or_error(
            executor=executor,
            allow_create=allow_slot_creation,
            slot=slot,
            logger=logger,
            detailed_gpu_info=detailed_gpu_info,
            gpu_services=gpu_services,
            storage=storage,
        )
        if isinstance(resolved, dict):
            return resolved
        resolved_payload: tuple[
            str,
            SlotPayloadDependencies,
            dict[str, JSONDict],
            JSONDict,
        ] = resolved
        slot_id, _deps, inventory, payload = resolved_payload
        if device_id not in inventory:
            return device_missing_error(device_id)
        device_info = inventory[device_id]
        entry = devices(payload).get(device_id)
        if not isinstance(entry, dict):
            return slot_empty_error(device_id, slot_id)
        boot_before = copy.deepcopy(entry.get("boot", {}))
        slots_value = entry.get("slots")
        if not isinstance(slots_value, dict):
            return slot_empty_error(device_id, slot_id)
        slot_entry = slots_value.get(slot_id)
        if not isinstance(slot_entry, dict):
            return slot_empty_error(device_id, slot_id)
        del slots_value[slot_id]
        boot = entry.get("boot", {})
        if isinstance(boot, dict) and boot.get("slot") == slot_id:
            entry["boot"] = disabled_boot_payload()
        remaining = any(
            isinstance(device_entry, dict) and device_entry.get("slots")
            for device_entry in devices(payload).values()
        )
        if remaining:
            storage.write_payload(payload)
        else:
            try_remove_slots_file(
                gpu_slots_path=gpu_slots_path,
                logger=logger,
                operation_context="hardware_presets.sync_clear_gpu_slot",
            )
        entry_after = devices(payload).get(device_id)
        if not isinstance(entry_after, dict):
            entry_after = empty_device_entry(device_info)
        entry_snapshot = copy.deepcopy(entry_after)
        boot_changed = entry_snapshot.get("boot", {}) != boot_before
    return {
        "success": True,
        "device_id": device_id,
        "slot": slot_id,
        "entry": entry_snapshot,
        "boot_changed": boot_changed,
    }
