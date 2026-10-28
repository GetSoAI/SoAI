"""SoAI - GPU slot device control state helpers [backend/hardware/presets/slot_control_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.types.json import is_json_value
from core.validation.boolean_coercion import coerce_bool_flag
from core.validation.booleans import parse_bool
from hardware.control.profiles import (
    GPU_SLOT_FILE_VERSION,
    GPU_SLOT_IDS,
    default_boot_payload,
    normalize_slot_identifier,
    sanitize_slot_entry,
)
from hardware.gpu_tuning.setting_modes import normalize_field_mode
from hardware.presets.inventory_snapshot import canonical_gpu_inventory
from hardware.presets.slot_format import has_unrecognized_gpu_slot_state

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "clear_slot_boot_preference",
    "device_control_state_has_values",
    "normalize_device_control_state",
    "update_device_control_state",
)


def normalize_device_control_state(entry: JSONDict) -> bool:
    changed = False
    field_modes = entry.get("field_modes")
    if not isinstance(field_modes, dict):
        entry["field_modes"], changed = ({}, True)
    else:
        normalized_field_modes: JSONDict = {}
        for field, mode_value in field_modes.items():
            if not isinstance(field, str):
                changed = True
                continue
            mode_text = normalize_field_mode(mode_value)
            if mode_text is None:
                changed = True
                continue
            normalized_field_modes[field] = mode_text
        if normalized_field_modes != field_modes:
            entry["field_modes"], changed = (normalized_field_modes, True)
    applied_settings = entry.get("applied_settings")
    if not isinstance(applied_settings, dict):
        entry["applied_settings"], changed = ({}, True)
    else:
        normalized_applied_settings: JSONDict = {}
        for field, value in applied_settings.items():
            if not isinstance(field, str):
                changed = True
                continue
            if is_json_value(value):
                normalized_applied_settings[field] = value
            else:
                changed = True
        if normalized_applied_settings != applied_settings:
            entry["applied_settings"], changed = (normalized_applied_settings, True)
    return changed


def update_device_control_state(
    entry: JSONDict,
    field_modes: Mapping[str, JSONValue],
    applied_settings: Mapping[str, JSONValue],
) -> bool:
    existing_modes = entry.get("field_modes")
    existing_modes = existing_modes if isinstance(existing_modes, dict) else {}
    updated_modes = dict(existing_modes)
    existing_applied_settings = entry.get("applied_settings")
    existing_applied_settings = (
        existing_applied_settings if isinstance(existing_applied_settings, dict) else {}
    )
    updated_applied_settings = dict(existing_applied_settings)
    changed = False
    unverified = entry.get("unverified_control_fields", [])
    retained_unverified = list(unverified) if isinstance(unverified, list) else []
    for field, mode_value in field_modes.items():
        mode_text = str(mode_value).strip().lower()
        if not mode_text or mode_text not in {"auto", "manual"}:
            continue
        if field in retained_unverified:
            retained_unverified.remove(field)
            changed = True
        if updated_modes.get(field) != mode_text:
            updated_modes[field], changed = (mode_text, True)
        if mode_text == "auto":
            if field in updated_applied_settings:
                del updated_applied_settings[field]
                changed = True
            continue
        applied_value = applied_settings.get(field)
        if is_json_value(applied_value) and updated_applied_settings.get(field) != applied_value:
            updated_applied_settings[field], changed = (applied_value, True)
    if changed:
        if retained_unverified:
            entry["unverified_control_fields"] = retained_unverified
        else:
            entry.pop("unverified_control_fields", None)
        entry["field_modes"] = updated_modes
        entry["applied_settings"] = updated_applied_settings
    return changed


def device_control_state_has_values(entry: JSONDict) -> bool:
    applied_settings = entry.get("applied_settings")
    return isinstance(applied_settings, dict) and bool(applied_settings)


LOGGER_NAME = "SoAI.hardware.presets.slot_control_state"


def normalize_device_entry(entry: JSONDict, device_info: JSONDict) -> bool:
    if has_unrecognized_gpu_slot_state(entry):
        return False
    changed = False
    if entry.get("gpu_index") != (gpu_index := device_info.get("gpu_index")):
        entry["gpu_index"], changed = (gpu_index, True)
    if (gpu_name := device_info.get("name")) and entry.get("name") != gpu_name:
        entry["name"], changed = (gpu_name, True)
    if (vendor := device_info.get("vendor")) and entry.get("vendor") != vendor:
        entry["vendor"], changed = (vendor, True)
    original_slots = entry.get("slots")
    if not isinstance(original_slots, dict):
        original_slots, changed = ({}, True)
    sanitized_slots = {}
    for slot_id in GPU_SLOT_IDS:
        if raw_slot_entry := original_slots.get(slot_id):
            if sanitized := sanitize_slot_entry(raw_slot_entry):
                sanitized_slots[slot_id] = sanitized
    if sanitized_slots != original_slots:
        entry["slots"], changed = (sanitized_slots, True)
    boot_entry = entry.get("boot")
    boot_entry_dict: JSONDict
    if not isinstance(boot_entry, dict):
        boot_entry_dict = default_boot_payload()
        changed = True
    else:
        boot_entry_dict = {}
        for key, value in boot_entry.items():
            if not isinstance(key, str):
                changed = True
                continue
            if is_json_value(value):
                boot_entry_dict[key] = value
            else:
                boot_entry_dict[key] = None
                changed = True
        boot_changed = False
        enabled = coerce_bool_flag(
            boot_entry_dict.get("enabled"),
            logger=get_logger(LOGGER_NAME),
            operation="hardware.presets.slot_storage.coerce_bool_flag",
            default=False,
            recover_message="Failed to parse boolean flag (non-critical).",
        )
        slot_value = boot_entry_dict.get("slot")
        normalized_slot = (
            normalize_slot_identifier(slot_value) if isinstance(slot_value, str | int) else None
        )
        if slot_value is not None and normalized_slot is None:
            enabled, normalized_slot, boot_changed = (False, None, True)
        if not enabled:
            normalized_slot = None
        if boot_entry_dict.get("enabled") != enabled:
            boot_entry_dict["enabled"], boot_changed = (enabled, True)
        if boot_entry_dict.get("slot") != normalized_slot:
            boot_entry_dict["slot"], boot_changed = (normalized_slot, True)
        for field in ("applied_signature", "applied_at"):
            value = boot_entry_dict.get(field)
            if value is not None and not isinstance(value, str):
                boot_entry_dict[field], boot_changed = (None, True)
        if boot_changed:
            entry["boot"], changed = (boot_entry_dict, True)
    if normalize_device_control_state(entry):
        changed = True
    return changed


def ensure_device_entry(payload: JSONDict, device_id: str, device_info: JSONDict) -> JSONDict:
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        devices = {}
        payload["devices"] = devices
    existing = devices.get(device_id)
    if not isinstance(existing, dict):
        existing = {
            "device_id": device_id,
            "gpu_index": device_info.get("gpu_index"),
            "name": device_info.get("name"),
            "slots": {},
            "boot": default_boot_payload(),
            "field_modes": {},
            "applied_settings": {},
        }
        if vendor := device_info.get("vendor"):
            existing["vendor"] = vendor
        devices[device_id] = existing
        return existing
    normalize_device_entry(existing, device_info)
    existing["device_id"] = device_id
    return existing


def update_control_state_for_device(
    payload: JSONDict,
    device_id: str,
    device_info: JSONDict,
    field_modes: Mapping[str, JSONValue],
    applied_settings: Mapping[str, JSONValue],
) -> bool:
    entry = ensure_device_entry(payload, device_id, device_info)
    return update_device_control_state(entry, field_modes, applied_settings)


def is_device_entry_empty(entry: JSONDict) -> bool:
    if has_unrecognized_gpu_slot_state(entry):
        return False
    if entry.get("unverified_control_fields"):
        return False
    slots = entry.get("slots")
    if isinstance(slots, dict):
        if any(bool(value) for value in slots.values()):
            return False
    boot = entry.get("boot")
    if isinstance(boot, dict):
        try:
            if parse_bool(boot.get("enabled"), default=False):
                return False
        except ValidationError:
            return False
    if isinstance(boot, dict) and any(
        boot.get(field) is not None for field in ("slot", "applied_signature", "applied_at")
    ):
        return False
    if bool(entry.get("field_modes")) or device_control_state_has_values(entry):
        return False
    return True


def is_slots_payload_empty(payload: JSONDict) -> bool:
    devices = payload.get("devices")
    return (
        not set(payload) - {"version", "devices", "recovery", "alias_history"}
        and not payload.get("recovery")
        and not payload.get("alias_history")
        and isinstance(devices, dict)
        and all(
            isinstance(entry, dict) and is_device_entry_empty(entry) for entry in devices.values()
        )
    )


def clear_slot_boot_preference(boot: JSONDict) -> None:
    parse_bool(boot.get("enabled"), default=False)
    boot.update(default_boot_payload())


def require_empty_payload_deletion_authority(payload: JSONDict, current: JSONDict) -> None:
    candidate = copy.deepcopy(current)
    current_devices = candidate.get("devices")
    if not isinstance(current_devices, dict):
        raise ValidationError("GPU deletion requires complete current device authority.")
    removed_slots = 0
    for entry in current_devices.values():
        if not isinstance(entry, dict):
            raise ValidationError("GPU deletion requires complete current device entries.")
        slots = entry.get("slots", {})
        if not isinstance(slots, dict):
            raise ValidationError("GPU deletion requires complete current saved slots.")
        removed_slots += len(slots)
        if slots:
            boot = entry.get("boot")
            boot_slot = boot.get("slot") if isinstance(boot, dict) else None
            if isinstance(boot, dict) and isinstance(boot_slot, str) and boot_slot in slots:
                clear_slot_boot_preference(boot)
            entry["slots"] = {}
    if removed_slots > 1 or candidate != payload:
        raise ValidationError("GPU deletion discarded authority beyond the final selected slot.")


def prune_slots_payload(
    payload: JSONDict,
    inventory: dict[str, JSONDict],
    *,
    retained_vendors: frozenset[str] = frozenset(),
    protected_device_ids: frozenset[str] = frozenset(),
) -> bool:
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        payload["devices"] = {}
        return True
    changed = False
    for device_id, entry in list(devices.items()):
        if device_id in protected_device_ids:
            continue
        if not isinstance(entry, dict):
            del devices[device_id]
            changed = True
            continue
        if device_id not in inventory:
            if entry.get("vendor") in retained_vendors:
                continue
            if is_device_entry_empty(entry):
                del devices[device_id]
                changed = True
            else:
                entry["offline"] = True
            continue
        device_info = inventory[device_id]
        if normalize_device_entry(entry, device_info):
            changed = True
        entry.pop("offline", None)
    for device_id, device_info in canonical_gpu_inventory(inventory).items():
        if device_id not in devices and device_id not in protected_device_ids:
            ensure_device_entry(payload, device_id, device_info)
            changed = True
    payload_version = payload.get("version")
    if payload_version != GPU_SLOT_FILE_VERSION:
        payload["version"], changed = (GPU_SLOT_FILE_VERSION, True)
    return changed
