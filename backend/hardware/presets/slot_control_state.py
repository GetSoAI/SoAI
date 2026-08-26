"""SoAI - GPU slot device control state helpers [backend/hardware/presets/slot_control_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.types.json import is_json_value
from hardware.gpu_tuning.setting_modes import normalize_field_mode

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
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
    for field, mode_value in field_modes.items():
        mode_text = str(mode_value).strip().lower()
        if not mode_text or mode_text not in {"auto", "manual"}:
            continue
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
        entry["field_modes"] = updated_modes
        entry["applied_settings"] = updated_applied_settings
    return changed


def device_control_state_has_values(entry: JSONDict) -> bool:
    applied_settings = entry.get("applied_settings")
    return isinstance(applied_settings, dict) and bool(applied_settings)
