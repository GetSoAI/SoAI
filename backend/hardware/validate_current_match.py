"""SoAI - GPU applied-settings comparison helpers [backend/hardware/validate_current_match.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.hardware.gpu_settings_contract import GPU_RESET_CLOCKS_FIELD
from hardware.gpu_tuning.service_parsing import coerce_gpu_setting_int
from hardware.gpu_tuning.setting_capabilities import setting_descriptor_for_key
from hardware.gpu_tuning.setting_modes import field_modes_match_current

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "settings_match_current",
    "settings_requiring_value_apply",
    "settings_values_match_current",
)


def _caps_entry(capabilities: Mapping[str, JSONValue], setting_key: str) -> JSONDict:
    descriptor = setting_descriptor_for_key(setting_key)
    if descriptor is None:
        return {}
    value = capabilities.get(descriptor.caps_key)
    return value if isinstance(value, dict) else {}


def _setting_matches_caps(value: JSONValue, caps_entry: JSONDict) -> bool:
    current = coerce_gpu_setting_int(caps_entry.get("current"), round_float_strings=True)
    default = coerce_gpu_setting_int(caps_entry.get("default"), round_float_strings=True)
    if isinstance(value, str) and value.lower() == "auto":
        if caps_entry.get("auto_requires_apply") is True:
            return False
        return current is not None and default is not None and current == default
    desired = coerce_gpu_setting_int(value, round_float_strings=True)
    return desired is not None and current is not None and current == desired


def _reset_clocks_matches_current(value: JSONValue) -> bool:
    if not value:
        return True
    return False


def settings_values_match_current(
    settings: Mapping[str, JSONValue],
    capabilities: Mapping[str, JSONValue] | None,
) -> bool:
    if not capabilities or not isinstance(settings, Mapping) or (not settings):
        return False
    for key, value in settings.items():
        if key == GPU_RESET_CLOCKS_FIELD:
            if not _reset_clocks_matches_current(value):
                return False
            continue
        if setting_descriptor_for_key(key) is None:
            return False
        if not _setting_matches_caps(value, _caps_entry(capabilities, key)):
            return False
    return True


def settings_requiring_value_apply(
    settings: Mapping[str, JSONValue],
    capabilities: Mapping[str, JSONValue] | None,
) -> JSONDict:
    if not capabilities:
        return dict(settings)
    pending: JSONDict = {}
    for key, value in settings.items():
        if key == GPU_RESET_CLOCKS_FIELD:
            if not _reset_clocks_matches_current(value):
                pending[key] = value
            continue
        if setting_descriptor_for_key(key) is None:
            pending[key] = value
            continue
        if not _setting_matches_caps(value, _caps_entry(capabilities, key)):
            pending[key] = value
    return pending


def settings_match_current(
    settings: Mapping[str, JSONValue],
    capabilities: Mapping[str, JSONValue] | None,
    *,
    requested_field_modes: Mapping[str, JSONValue] | None = None,
    current_field_modes: Mapping[str, JSONValue] | None = None,
) -> bool:
    if not settings_values_match_current(settings, capabilities):
        return False
    if requested_field_modes is None and current_field_modes is None:
        return True
    return field_modes_match_current(
        settings,
        requested_field_modes,
        current_field_modes,
    )
