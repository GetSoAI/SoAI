"""SoAI - GPU slot storage and normalization [backend/hardware/presets/slot_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_writes import atomic_write_text
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_pretty_sorted_strict
from core.serialization.json_parsing import parse_json_dict
from core.types.json import is_json_value
from core.validation.boolean_coercion import coerce_bool_flag
from hardware.control.profiles import (
    GPU_SLOT_FILE_VERSION,
    GPU_SLOT_IDS,
    default_boot_payload,
    normalize_slot_identifier,
    sanitize_slot_entry,
)
from hardware.presets.slot_control_state import (
    device_control_state_has_values,
    normalize_device_control_state,
    update_device_control_state,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "GpuSlotStorageManager",
    "GpuSlotStorageManagerDependencies",
    "ensure_device_entry",
    "is_device_entry_empty",
    "normalize_device_entry",
    "prune_slots_payload",
    "update_control_state_for_device",
)

LOGGER_NAME = "SoAI.hardware.presets.slot_storage"
OPERATION = "gpu_slot_storage_manager.read_payload"


@dataclass(frozen=True, slots=True)
class GpuSlotStorageManagerDependencies:
    path: str
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GpuSlotStorageManagerDependencies",
            logger=self.logger,
            path=self.path,
        )


class GpuSlotStorageManager:
    def __init__(self, deps: GpuSlotStorageManagerDependencies) -> None:
        self._path = deps.path
        self.lock = threading.RLock()
        self.logger = deps.logger

    def read_payload(self) -> tuple[JSONDict, bool]:
        path_exists = os.path.exists(self._path)
        payload: JSONDict = {"version": GPU_SLOT_FILE_VERSION, "devices": {}}
        if path_exists:
            try:
                with open_text(self._path, encoding="utf-8") as handle:
                    loaded = parse_json_dict(handle.read(), field="GPU slot metadata")
                    if loaded.get("version") == GPU_SLOT_FILE_VERSION:
                        payload = loaded
            except (OSError, ValidationError) as exception:
                log_exception(
                    self.logger,
                    exception,
                    message="Failed to load GPU slot metadata",
                    operation=OPERATION,
                    details={"path": self._path},
                )
                try:
                    os.remove(self._path)
                except OSError as removal_error:
                    log_exception(
                        self.logger,
                        removal_error,
                        message="Could not remove corrupted GPU slot metadata file",
                        operation=OPERATION,
                        details={"path": self._path},
                    )
        return (payload, path_exists)

    def write_payload(self, payload: JSONDict) -> None:
        def _writer(handle: io.TextIOBase) -> None:
            handle.write(serialize_json_pretty_sorted_strict(payload))

        atomic_write_text(self._path, _writer, mode="w", encoding="utf-8")


def normalize_device_entry(entry: JSONDict, device_info: JSONDict) -> bool:
    changed = False
    if entry.get("gpu_index") != (gpu_index := device_info.get("gpu_index")):
        entry["gpu_index"], changed = (gpu_index, True)
    if (gpu_name := device_info.get("name")) and entry.get("name") != gpu_name:
        entry["name"], changed = (gpu_name, True)
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
    slots = entry.get("slots")
    if isinstance(slots, dict):
        if any(bool(value) for value in slots.values()):
            return False
    boot = entry.get("boot")
    if isinstance(boot, dict) and coerce_bool_flag(
        boot.get("enabled"),
        logger=get_logger(LOGGER_NAME),
        operation="hardware.presets.slot_storage.coerce_bool_flag",
        default=False,
        recover_message="Failed to parse boolean flag (non-critical).",
    ):
        return False
    if device_control_state_has_values(entry):
        return False
    return True


def prune_slots_payload(payload: JSONDict, inventory: dict[str, JSONDict]) -> bool:
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        payload["devices"] = {}
        return True
    changed = False
    for device_id, entry in list(devices.items()):
        if not isinstance(entry, dict):
            del devices[device_id]
            changed = True
            continue
        if device_id not in inventory:
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
    for device_id, device_info in inventory.items():
        if device_id not in devices:
            ensure_device_entry(payload, device_id, device_info)
            changed = True
    payload_version = payload.get("version")
    if payload_version != GPU_SLOT_FILE_VERSION:
        payload["version"], changed = (GPU_SLOT_FILE_VERSION, True)
    return changed
