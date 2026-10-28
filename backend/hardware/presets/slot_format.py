"""SoAI - GPU slot format validation and migration [backend/hardware/presets/slot_format.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import hashlib
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.hardware.gpu_control_types import (
    GPUSlotReadError,
    GPUSlotReadFailure,
    GPUSlotReadResult,
    GPUSlotReadState,
)
from core.hardware.gpu_recovery_records import (
    GPURecoveryRecord,
    GPUStartupLegacyRecoveryRecord,
    GPUStartupRecoveryRecord,
)
from core.hardware.gpu_settings_contract import GPU_DIRECT_SETTING_FIELDS, GPU_SETTING_FIELDS
from core.serialization.json_parsing import MAX_JSON_NESTING_DEPTH, parse_json_value
from core.types.json_value import require_json_dict
from core.validation.strict_integer import is_strict_int
from hardware.control.profiles import GPU_SLOT_FILE_VERSION, GPU_SLOT_IDS, default_boot_payload
from hardware.gpu_tuning.setting_modes import has_unrecognized_field_modes
from hardware.presets.gpu_recovery_format import decode_gpu_recovery_record
from hardware.presets.slot_alias_history import validate_alias_history

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "decode_gpu_slot_payload",
    "has_unrecognized_gpu_slot_state",
    "validate_gpu_slot_payload",
)


def has_unrecognized_gpu_slot_state(entry: JSONDict) -> bool:
    known_fields = {
        "device_id",
        "gpu_index",
        "name",
        "vendor",
        "offline",
        "slots",
        "boot",
        "field_modes",
        "applied_settings",
        "unverified_control_fields",
    }
    if set(entry) - known_fields:
        return True
    boot = entry.get("boot", {})
    slots = entry.get("slots", {})
    if not isinstance(boot, dict) or set(boot) - set(default_boot_payload()):
        return True
    if not isinstance(slots, dict) or set(slots) - set(GPU_SLOT_IDS):
        return True
    field_modes = entry.get("field_modes", {})
    applied_settings = entry.get("applied_settings", {})
    if (
        has_unrecognized_field_modes(field_modes)
        or not isinstance(applied_settings, dict)
        or set(applied_settings) - set(GPU_DIRECT_SETTING_FIELDS)
    ):
        return True
    slot_fields = {"settings", "field_modes", "saved_at", "last_applied_at", "signature"}
    for slot in slots.values():
        if not isinstance(slot, dict) or set(slot) - slot_fields:
            return True
        settings = slot.get("settings", {})
        modes = slot.get("field_modes", {})
        if (
            not isinstance(settings, dict)
            or set(settings) - set(GPU_SETTING_FIELDS)
            or has_unrecognized_field_modes(modes)
        ):
            return True
    return False


def decode_gpu_slot_payload(raw: bytes) -> GPUSlotReadResult:
    try:
        parsed = parse_json_value(
            raw,
            field="GPU slot metadata",
            max_depth=MAX_JSON_NESTING_DEPTH,
            strict_utf8=True,
            reject_duplicate_keys=True,
        )
        payload = require_json_dict(parsed, label="GPU slot metadata")
        records = validate_gpu_slot_payload(payload)
    except GPUSlotReadError:
        raise
    except (ValidationError, StateError, ValueError) as exception:
        raise GPUSlotReadError(GPUSlotReadFailure.MALFORMED) from exception
    source_format = payload["version"]
    if not is_strict_int(source_format):
        raise GPUSlotReadError(GPUSlotReadFailure.MALFORMED)
    migrated = copy.deepcopy(payload)
    if source_format == 1:
        migrated["version"] = GPU_SLOT_FILE_VERSION
        migrated["recovery"] = {}
    return GPUSlotReadResult(
        payload=migrated,
        state=GPUSlotReadState.VALID,
        source_format=source_format,
        revision=hashlib.sha256(raw).hexdigest(),
        migration_required=source_format == 1,
        recovery_records=records,
    )


def validate_gpu_slot_payload(
    payload: JSONDict,
) -> tuple[GPURecoveryRecord | GPUStartupRecoveryRecord | GPUStartupLegacyRecoveryRecord, ...]:
    version = payload.get("version")
    if not is_strict_int(version):
        raise ValidationError("GPU slot format must be an integer.")
    if version not in (1, GPU_SLOT_FILE_VERSION):
        raise GPUSlotReadError(GPUSlotReadFailure.UNSUPPORTED_FORMAT)
    validate_alias_history(payload)
    devices = require_json_dict(payload.get("devices", {}), label="GPU slot devices")
    for device_id, value in devices.items():
        if not device_id:
            raise ValidationError("GPU slot device identifier must not be empty.")
        entry = require_json_dict(value, label="GPU slot device")
        unverified = entry.get("unverified_control_fields", [])
        if not isinstance(unverified, list) or any(
            not isinstance(field, str) or field not in GPU_DIRECT_SETTING_FIELDS
            for field in unverified
        ):
            raise ValidationError("GPU unverified control fields must be recognized settings.")
        if "device_id" in entry and entry["device_id"] != device_id:
            raise ValidationError("GPU slot device identifier conflicts with its key.")
        for field in ("boot", "field_modes", "applied_settings"):
            if field in entry:
                require_json_dict(entry[field], label=field)
        slots = require_json_dict(entry.get("slots", {}), label="GPU saved slots")
        for slot in slots.values():
            profile = require_json_dict(slot, label="GPU saved slot")
            settings = require_json_dict(profile.get("settings"), label="GPU slot settings")
            if not settings:
                raise ValidationError("GPU slot settings must not be empty.")
            if "field_modes" in profile:
                require_json_dict(profile["field_modes"], label="GPU slot field modes")
            for field in ("signature", "saved_at", "last_applied_at"):
                if (
                    field in profile
                    and profile[field] is not None
                    and not isinstance(profile[field], str)
                ):
                    raise ValidationError("GPU saved slot metadata must be text or null.")
    if version == 1:
        if "recovery" in payload:
            raise ValidationError("GPU slot format1 cannot carry recovery authority.")
        return ()
    recovery = require_json_dict(payload.get("recovery"), label="GPU recovery")
    return tuple(
        decode_gpu_recovery_record(device_id, record) for device_id, record in recovery.items()
    )
