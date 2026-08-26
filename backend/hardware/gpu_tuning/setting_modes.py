"""SoAI - GPU setting mode normalization and comparison [backend/hardware/gpu_tuning/setting_modes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.hardware.gpu_settings_contract import (
    GPU_DIRECT_SETTING_FIELDS,
    GPU_RESET_CLOCKS_FIELD,
    GPU_SETTING_CORE_CLOCK_FIELD,
    GPU_SETTING_MEM_CLOCK_FIELD,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "default_field_modes_for_settings",
    "derive_field_modes_from_settings",
    "field_modes_mapping_or_none",
    "field_modes_match_current",
    "normalize_field_mode",
    "normalize_field_mode_mapping",
    "normalize_field_modes_for_settings",
    "normalize_field_modes_value_for_settings",
    "read_device_field_modes",
)


def normalize_field_mode(value: JSONValue) -> str | None:
    if not isinstance(value, str):
        return None
    mode_text = value.strip().lower()
    if mode_text not in {"auto", "manual"}:
        return None
    return mode_text


def derive_field_modes_from_settings(settings: Mapping[str, JSONValue]) -> JSONDict:
    field_modes: JSONDict = {}
    for field in GPU_DIRECT_SETTING_FIELDS:
        if field not in settings:
            continue
        field_modes[field] = (
            "auto"
            if isinstance(settings.get(field), str) and str(settings[field]).lower() == "auto"
            else "manual"
        )
    if settings.get(GPU_RESET_CLOCKS_FIELD) is True:
        field_modes[GPU_SETTING_CORE_CLOCK_FIELD] = "auto"
        field_modes[GPU_SETTING_MEM_CLOCK_FIELD] = "auto"
    return field_modes


def default_field_modes_for_settings(settings: Mapping[str, JSONValue]) -> JSONDict:
    field_modes: JSONDict = {}
    for field in GPU_DIRECT_SETTING_FIELDS:
        if field in settings:
            field_modes[field] = "auto"
    if settings.get(GPU_RESET_CLOCKS_FIELD) is True:
        field_modes[GPU_SETTING_CORE_CLOCK_FIELD] = "auto"
        field_modes[GPU_SETTING_MEM_CLOCK_FIELD] = "auto"
    return field_modes


def normalize_field_modes_for_settings(
    settings: Mapping[str, JSONValue],
    field_modes: Mapping[str, JSONValue] | None,
) -> JSONDict:
    normalized = default_field_modes_for_settings(settings)
    if not isinstance(field_modes, Mapping):
        return normalized
    for field in GPU_DIRECT_SETTING_FIELDS:
        if field not in normalized:
            continue
        mode_text = normalize_field_mode(field_modes.get(field))
        if mode_text is not None:
            normalized[field] = mode_text
    return normalized


def field_modes_mapping_or_none(value: JSONValue) -> Mapping[str, JSONValue] | None:
    return value if isinstance(value, Mapping) else None


def normalize_field_mode_mapping(value: JSONValue) -> JSONDict:
    normalized: JSONDict = {}
    if not isinstance(value, Mapping):
        return normalized
    for field, mode_value in value.items():
        mode_text = normalize_field_mode(mode_value)
        if isinstance(field, str) and mode_text is not None:
            normalized[field] = mode_text
    return normalized


def normalize_field_modes_value_for_settings(
    settings: Mapping[str, JSONValue],
    value: JSONValue,
) -> JSONDict:
    return normalize_field_modes_for_settings(settings, field_modes_mapping_or_none(value))


def read_device_field_modes(
    entry: Mapping[str, JSONValue] | None,
    settings: Mapping[str, JSONValue],
) -> JSONDict:
    if not isinstance(entry, Mapping):
        return default_field_modes_for_settings(settings)
    return normalize_field_modes_value_for_settings(settings, entry.get("field_modes"))


def field_modes_match_current(
    settings: Mapping[str, JSONValue],
    requested_field_modes: Mapping[str, JSONValue] | None,
    current_field_modes: Mapping[str, JSONValue] | None,
) -> bool:
    expected = normalize_field_modes_for_settings(settings, requested_field_modes)
    current = normalize_field_modes_for_settings(settings, current_field_modes)
    for field in expected:
        if current.get(field) != expected.get(field):
            return False
    return True
