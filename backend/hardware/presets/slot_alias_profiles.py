"""SoAI - Lossless GPU alias profile consolidation [backend/hardware/presets/slot_alias_profiles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import (
    GPU_DIRECT_SETTING_FIELDS,
    validate_gpu_reset_clock_conflict,
)
from core.timing.formatting import parse_iso_datetime_optional
from core.types.json import JSONDict, JSONValue
from core.types.json_value import require_json_dict
from core.validation.strict_numbers import require_finite_float_strict
from hardware.control.profiles import GPU_SLOT_IDS, default_boot_payload, sanitize_slot_entry
from hardware.presets.slot_alias_history import preserve_alias_sources
from hardware.presets.slot_control_state import is_device_entry_empty
from hardware.presets.slot_format import has_unrecognized_gpu_slot_state

__all__ = ("consolidate_alias_profiles", "project_alias_history")


def _recognized_profile(slot_id: str, profile: JSONValue) -> JSONDict | None:
    if not isinstance(profile, dict) or has_unrecognized_gpu_slot_state(
        {"slots": {slot_id: profile}}
    ):
        return None
    settings = profile.get("settings")
    if not isinstance(settings, dict) or not settings:
        return None
    for field, value in settings.items():
        if field == "reset_clocks":
            if not isinstance(value, bool):
                return None
        elif value != "auto":
            try:
                require_finite_float_strict(
                    value, error_message="GPU profile value must be finite."
                )
            except ValidationError:
                return None
    try:
        validate_gpu_reset_clock_conflict(
            reset_clocks=settings.get("reset_clocks") is True,
            core_clock=settings.get("core_clock"),
            mem_clock=settings.get("mem_clock"),
        )
    except ValidationError:
        return None
    for field in ("saved_at", "last_applied_at"):
        value = profile.get(field)
        if value is not None and (
            not isinstance(value, str) or parse_iso_datetime_optional(value) is None
        ):
            return None
    signature = profile.get("signature")
    if signature is not None and (not isinstance(signature, str) or not signature.strip()):
        return None
    return copy.deepcopy(profile)


def _profile_state(profile: JSONDict) -> JSONDict:
    return {"settings": profile.get("settings"), "field_modes": profile.get("field_modes", {})}


def _matching_profile_slot(slots: JSONDict, profile: JSONDict) -> str | None:
    return next(
        (
            slot_id
            for slot_id, existing in slots.items()
            if isinstance(existing, dict) and _profile_state(existing) == _profile_state(profile)
        ),
        None,
    )


def _allocate_profiles(sources: list[tuple[str, JSONDict]]) -> tuple[JSONDict, dict[str, str]]:
    slots: JSONDict = {}
    assignments: dict[str, str] = {}
    deferred: list[tuple[str, JSONDict]] = []
    for source_id, entry in sources:
        source_slots = require_json_dict(entry.get("slots", {}), label="GPU saved slots")
        for slot_id in GPU_SLOT_IDS:
            profile = _recognized_profile(slot_id, source_slots.get(slot_id))
            if profile is None:
                continue
            profile = sanitize_slot_entry(profile)
            if profile is None:
                continue
            reference = f"{source_id}/{slot_id}"
            if source_id == sources[0][0] and slot_id not in slots:
                slots[slot_id] = profile
                assignments[reference] = slot_id
                continue
            identical = _matching_profile_slot(slots, profile)
            if identical is not None:
                assignments[reference] = identical
            elif slot_id not in slots:
                slots[slot_id] = profile
                assignments[reference] = slot_id
            else:
                deferred.append((reference, profile))
    for reference, profile in deferred:
        identical = _matching_profile_slot(slots, profile)
        destination = identical or next(
            (slot_id for slot_id in GPU_SLOT_IDS if slot_id not in slots), None
        )
        if destination is not None:
            slots[destination] = slots.get(destination, profile)
            assignments[reference] = destination
    return slots, assignments


def _boot_preference(
    sources: list[tuple[str, JSONDict]], assignments: dict[str, str]
) -> tuple[JSONDict, bool]:
    preferences: list[tuple[bool, str | None]] = []
    invalid = False
    for source_id, entry in sources:
        boot = require_json_dict(entry.get("boot", {}), label="GPU slot boot")
        enabled = boot.get("enabled", False)
        slot = boot.get("slot")
        destination = assignments.get(f"{source_id}/{slot}") if isinstance(slot, str) else None
        if (
            not isinstance(enabled, bool)
            or set(boot) - set(default_boot_payload())
            or (enabled and destination is None)
        ):
            invalid = True
        preferences.append((enabled is True, destination if enabled else None))
    conflict = invalid or len(set(preferences)) > 1
    boot = default_boot_payload()
    if preferences and not conflict:
        boot["enabled"], boot["slot"] = preferences[0]
    return boot, conflict


def consolidate_alias_profiles(
    payload: JSONDict, canonical: str, sources: list[tuple[str, JSONDict]]
) -> JSONDict:
    ordered = sorted(
        (source for source in sources if not is_device_entry_empty(source[1])),
        key=lambda source: (source[0] != canonical, source[0]),
    )
    slots, assignments = _allocate_profiles(ordered)
    boot, boot_conflict = _boot_preference(ordered, assignments)
    authority: JSONDict = {"device_id": canonical, "slots": slots, "boot": boot}
    modes: JSONDict = {}
    applied: JSONDict = {}
    uncertain: list[JSONValue] = []
    unverified_fields: set[str] = set()
    for _, entry in ordered:
        retained = entry.get("unverified_control_fields", [])
        if isinstance(retained, list):
            unverified_fields.update(field for field in retained if isinstance(field, str))
    for field in GPU_DIRECT_SETTING_FIELDS:
        source_modes = [
            require_json_dict(entry.get("field_modes", {}), label="GPU modes").get(field)
            for _, entry in ordered
        ]
        source_values = [
            require_json_dict(entry.get("applied_settings", {}), label="GPU applied settings").get(
                field
            )
            for _, entry in ordered
        ]
        if (
            field not in unverified_fields
            and all(mode == source_modes[0] for mode in source_modes)
            and all(value == source_values[0] for value in source_values)
            and source_modes[0] in (None, "auto", "manual")
        ):
            if source_modes[0] is not None:
                modes[field] = source_modes[0]
            if source_values[0] is not None:
                applied[field] = source_values[0]
        else:
            uncertain.append(field)
    authority["field_modes"], authority["applied_settings"] = modes, applied
    if uncertain:
        authority["unverified_control_fields"] = uncertain
    preserve_alias_sources(payload, canonical, dict(sources), boot_conflict=boot_conflict)
    return authority


def project_alias_history(payload: JSONDict, canonical: str) -> JSONDict:
    history = require_json_dict(payload.get("alias_history", {}), label="GPU alias history")
    records = require_json_dict(history.get(canonical, {}), label="GPU alias history records")
    profiles: list[JSONValue] = []
    boot_conflict = False
    for revision, value in sorted(records.items()):
        record = require_json_dict(value, label="GPU alias history record")
        boot_conflict = boot_conflict or record.get("boot_conflict") is True
        sources = require_json_dict(record.get("sources"), label="GPU alias history sources")
        for source_id, source_value in sorted(sources.items()):
            entry = require_json_dict(source_value, label="GPU preserved source")
            source_slots = require_json_dict(entry.get("slots", {}), label="GPU saved slots")
            for slot_id, profile in sorted(source_slots.items()):
                profiles.append(
                    {
                        "id": f"{revision}/{source_id}/{slot_id}",
                        "source_device_id": source_id,
                        "source_slot": slot_id,
                        "profile": _recognized_profile(slot_id, profile),
                        "original": copy.deepcopy(profile),
                    }
                )
    return {"recovered_profiles": profiles, "boot_conflict": boot_conflict}
