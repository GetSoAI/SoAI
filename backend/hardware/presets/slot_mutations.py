"""SoAI - GPU slot mutations and dirty flag handling [backend/hardware/presets/slot_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.filesystem.atomic_writes import atomic_write_text_content
from core.hardware.protocols import GpuSlotStorageManagerProtocol
from core.logging.protocols import LoggerProtocol
from core.timing.formatting import utc_now_iso
from hardware.control.profiles import compute_slot_signature, default_boot_payload
from hardware.gpu_tuning.setting_modes import normalize_field_modes_for_settings

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "record_slot_application_unlocked",
    "store_slot_unlocked",
    "touch_dirty_flag",
)

OPERATION = "hardware.presets.slot_mutations.touch_dirty_flag"


def store_slot_unlocked(
    storage: GpuSlotStorageManagerProtocol,
    payload: JSONDict,
    device_id: str,
    slot_id: str,
    settings: JSONDict,
    field_modes: JSONDict | None,
    saved_at: str | None = None,
) -> JSONDict:
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        devices = {}
        payload["devices"] = devices
    entry = devices.get(device_id)
    if not isinstance(entry, dict):
        entry = {
            "device_id": device_id,
            "gpu_index": None,
            "name": None,
            "slots": {},
            "boot": default_boot_payload(),
            "field_modes": {},
        }
        devices[device_id] = entry
    slots = entry.get("slots")
    if not isinstance(slots, dict):
        slots = {}
        entry["slots"] = slots
    stored_settings = dict(settings)
    stored_field_modes = normalize_field_modes_for_settings(stored_settings, field_modes)
    signature = compute_slot_signature(stored_settings, stored_field_modes)
    if not isinstance(saved_at, str) or not saved_at:
        saved_at = utc_now_iso()
    slots[slot_id] = {
        "settings": stored_settings,
        "field_modes": stored_field_modes,
        "saved_at": saved_at,
        "last_applied_at": None,
        "signature": signature,
    }
    storage.write_payload(payload)
    return {"signature": signature, "saved_at": saved_at}


def record_slot_application_unlocked(
    storage: GpuSlotStorageManagerProtocol,
    payload: JSONDict,
    device_id: str,
    slot_id: str | None,
    signature: str | None,
    applied_at: str | None,
) -> tuple[bool, JSONDict | None]:
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        return (False, None)
    entry = devices.get(device_id)
    if not isinstance(entry, dict):
        return (False, None)
    boot = entry.get("boot")
    if not isinstance(boot, dict):
        boot = default_boot_payload()
        entry["boot"] = boot
    boot_changed = False
    if slot_id is None:
        if boot.get("applied_signature") is not None:
            boot["applied_signature"], boot_changed = (None, True)
        if boot.get("applied_at") is not None:
            boot["applied_at"], boot_changed = (None, True)
    else:
        if boot.get("applied_signature") != signature:
            boot["applied_signature"], boot_changed = (signature, True)
        if boot.get("applied_at") != applied_at:
            boot["applied_at"], boot_changed = (applied_at, True)
    if slot_id:
        slots = entry.get("slots")
        if isinstance(slots, dict):
            slot_entry = slots.get(slot_id)
            if isinstance(slot_entry, dict):
                slot_entry["last_applied_at"] = applied_at
    if boot_changed:
        entry["boot"] = boot
    if boot_changed:
        storage.write_payload(payload)
    return (boot_changed, entry.copy())


def touch_dirty_flag(*, dirty_flag_path: str, logger: LoggerProtocol) -> None:
    try:
        atomic_write_text_content(
            dirty_flag_path,
            "",
            encoding="utf-8",
            errors="strict",
            ensure_parent=False,
            fsync=True,
        )
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to update GPU dirty flag",
            operation=OPERATION,
            details={"path": dirty_flag_path},
        )
