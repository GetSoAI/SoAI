"""SoAI - GPU direct apply control state helpers [backend/hardware/gpu_tuning/direct_control_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from hardware.gpu_tuning.setting_modes import read_device_field_modes

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "applied_settings_from_sanitized",
    "control_state_matches",
)


def applied_settings_from_sanitized(settings: JSONDict, field_modes: JSONDict) -> JSONDict:
    applied_settings: JSONDict = {}
    for field, mode_value in field_modes.items():
        if mode_value != "manual":
            continue
        value = settings.get(field)
        if isinstance(value, int):
            applied_settings[field] = value
    return applied_settings


def control_state_matches(
    *,
    device_entry: JSONDict | None,
    requested_settings: JSONDict,
    requested_field_modes: JSONDict,
    requested_applied_settings: JSONDict,
) -> bool:
    if device_entry is None:
        return False
    if read_device_field_modes(device_entry, requested_settings) != requested_field_modes:
        return False
    raw_applied_settings = device_entry.get("applied_settings")
    current_applied_settings = (
        raw_applied_settings if isinstance(raw_applied_settings, dict) else {}
    )
    for field, mode_value in requested_field_modes.items():
        if mode_value == "auto":
            if field in current_applied_settings:
                return False
            continue
        if current_applied_settings.get(field) != requested_applied_settings.get(field):
            return False
    return True
