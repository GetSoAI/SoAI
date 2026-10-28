"""SoAI - Saved GPU control state authority and verified projections [backend/hardware/gpu_tuning/control_saved_state_authority.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.types.json_value import require_json_dict
from hardware.control.profiles import default_boot_payload

if TYPE_CHECKING:
    from core.hardware.gpu_recovery_records import GPURecoveryRecord
    from core.types.json import JSONDict

__all__ = ("control_state_digest", "require_saved_control_authority", "apply_verified_user_state")


def control_state_digest(payload: JSONDict, device_id: str) -> str:
    devices = require_json_dict(payload.get("devices"), label="GPU saved devices")
    entry_value = devices.get(device_id)
    if entry_value is None:
        return hashlib.sha256(serialize_json_compact_stable(None).encode("utf-8")).hexdigest()
    entry = require_json_dict(entry_value, label="GPU saved device")
    state: JSONDict = {
        field: entry.get(field) for field in ("field_modes", "applied_settings", "slots", "boot")
    }
    if entry.get("unverified_control_fields"):
        state["unverified_control_fields"] = entry["unverified_control_fields"]
    return hashlib.sha256(serialize_json_compact_stable(state).encode("utf-8")).hexdigest()


def require_saved_control_authority(payload: JSONDict, record: GPURecoveryRecord) -> None:
    intent = record.commit_intent
    if (
        intent is None
        or control_state_digest(payload, record.device_id) != intent.expected_control_state_digest
    ):
        raise ValidationError("GPU saved control authority changed after preparation.")
    if intent.slot_id is not None:
        devices = require_json_dict(payload.get("devices"), label="GPU saved devices")
        entry = require_json_dict(devices.get(record.device_id), label="GPU saved device")
        slots = require_json_dict(entry.get("slots"), label="GPU saved slots")
        slot = require_json_dict(slots.get(intent.slot_id), label="GPU saved slot")
        if slot.get("signature") != intent.slot_signature:
            raise ValidationError("GPU saved slot signature changed after preparation.")


def apply_verified_user_state(
    payload: JSONDict, record: GPURecoveryRecord, completed_at: str
) -> None:
    intent = record.commit_intent
    if intent is None:
        raise ValidationError("GPU user-state commit requires explicit intent.")
    devices = require_json_dict(payload.get("devices"), label="GPU saved devices")
    existing = devices.get(record.device_id)
    entry: JSONDict = (
        require_json_dict(existing, label="GPU saved device")
        if existing is not None
        else {"device_id": record.device_id, "slots": {}, "boot": default_boot_payload()}
    )
    devices[record.device_id] = entry
    payload["devices"] = devices
    modes = require_json_dict(entry.get("field_modes", {}), label="GPU saved modes")
    applied = require_json_dict(entry.get("applied_settings", {}), label="GPU applied settings")
    for field in intent.user_fields:
        mode = record.requested_modes[field]
        modes[field] = mode
        if mode == "manual":
            applied[field] = record.requested_settings[field]
        else:
            applied.pop(field, None)
    unverified = entry.get("unverified_control_fields", [])
    if isinstance(unverified, list):
        remaining = [field for field in unverified if field not in intent.user_fields]
        if remaining:
            entry["unverified_control_fields"] = remaining
        else:
            entry.pop("unverified_control_fields", None)
    entry["field_modes"], entry["applied_settings"] = modes, applied
    if intent.slot_id is None:
        if intent.apply_at_boot is False and "boot" in entry:
            boot = require_json_dict(entry["boot"], label="GPU boot preferences")
            boot["enabled"] = False
            entry["boot"] = boot
        return
    slots = require_json_dict(entry.get("slots"), label="GPU saved slots")
    slot = require_json_dict(slots.get(intent.slot_id), label="GPU saved slot")
    slot["last_applied_at"] = completed_at
    slots[intent.slot_id] = slot
    entry["slots"] = slots
    boot = require_json_dict(entry.get("boot", {}), label="GPU boot preferences")
    if intent.apply_at_boot is not None:
        boot = default_boot_payload()
        boot["enabled"] = intent.apply_at_boot
        boot["slot"] = intent.slot_id if intent.apply_at_boot else None
    if boot.get("enabled") is True and boot.get("slot") == intent.slot_id:
        boot["applied_signature"], boot["applied_at"] = intent.slot_signature, completed_at
    entry["boot"] = boot
