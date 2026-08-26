"""SoAI - GPU tuning effective control state resolution [backend/hardware/gpu_tuning/effective_control_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import GPU_CLOCK_SETTING_FIELDS
from core.validation.numbers import coerce_int_from_json
from hardware.gpu_tuning.direct_control_state import (
    applied_settings_from_sanitized,
    control_state_matches,
)
from hardware.gpu_tuning.service_parsing import coerce_gpu_setting_int
from hardware.gpu_tuning.setting_capabilities import (
    gpu_setting_descriptors,
    setting_descriptor_for_key,
)
from hardware.gpu_tuning.setting_modes import read_device_field_modes
from hardware.validate_current_match import (
    settings_requiring_value_apply,
    settings_values_match_current,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_apply_settings_for_modes",
    "build_effective_capabilities",
    "control_state_active_for_request",
    "requested_applied_settings_for_modes",
    "settings_requiring_effective_apply",
    "settings_values_match_effective",
)


def requested_applied_settings_for_modes(settings: JSONDict, field_modes: JSONDict) -> JSONDict:
    return applied_settings_from_sanitized(settings, field_modes)


def build_apply_settings_for_modes(settings: JSONDict, field_modes: JSONDict) -> JSONDict:
    apply_settings: JSONDict = {}
    for field, value in settings.items():
        descriptor = setting_descriptor_for_key(field)
        if descriptor is None:
            apply_settings[field] = value
            continue
        mode_value = field_modes.get(field)
        if mode_value == "auto":
            apply_settings[field] = "auto"
            continue
        if mode_value == "manual":
            if isinstance(value, int):
                apply_settings[field] = value
                continue
            raise ValidationError(f"Manual mode for {field} requires a numeric value.")
        apply_settings[field] = value
    return apply_settings


def build_effective_capabilities(
    capabilities: Mapping[str, JSONValue] | None,
    *,
    current_field_modes: Mapping[str, JSONValue] | None,
    applied_settings: Mapping[str, JSONValue] | None,
) -> JSONDict | None:
    if not isinstance(capabilities, Mapping):
        return None
    effective: JSONDict = dict(capabilities)
    applied: Mapping[str, JSONValue] = (
        applied_settings if isinstance(applied_settings, Mapping) else {}
    )
    modes: Mapping[str, JSONValue] = (
        current_field_modes if isinstance(current_field_modes, Mapping) else {}
    )
    for descriptor in gpu_setting_descriptors():
        if descriptor.request_key not in GPU_CLOCK_SETTING_FIELDS:
            continue
        if modes.get(descriptor.request_key) != "manual":
            continue
        applied_value = coerce_int_from_json(applied.get(descriptor.request_key))
        if applied_value is None:
            continue
        caps_entry = effective.get(descriptor.caps_key)
        if not isinstance(caps_entry, dict):
            continue
        next_entry = dict(caps_entry)
        next_entry["current"] = applied_value
        effective[descriptor.caps_key] = next_entry
    return effective


def control_state_active_for_request(
    *,
    device_entry: JSONDict | None,
    settings: JSONDict,
    requested_field_modes: JSONDict,
) -> bool:
    requested_applied_settings = requested_applied_settings_for_modes(
        settings,
        requested_field_modes,
    )
    return control_state_matches(
        device_entry=device_entry,
        requested_settings=settings,
        requested_field_modes=requested_field_modes,
        requested_applied_settings=requested_applied_settings,
    )


def settings_values_match_effective(
    settings: JSONDict,
    capabilities: Mapping[str, JSONValue] | None,
    *,
    device_entry: JSONDict | None,
    requested_field_modes: JSONDict,
) -> bool:
    effective_capabilities = _comparable_capabilities_for_request(
        capabilities,
        settings,
        device_entry=device_entry,
        requested_field_modes=requested_field_modes,
    )
    return settings_values_match_current(settings, effective_capabilities)


def settings_requiring_effective_apply(
    settings: JSONDict,
    capabilities: Mapping[str, JSONValue] | None,
    *,
    device_entry: JSONDict | None,
    requested_field_modes: JSONDict,
) -> JSONDict:
    effective_capabilities = _comparable_capabilities_for_request(
        capabilities,
        settings,
        device_entry=device_entry,
        requested_field_modes=requested_field_modes,
    )
    return settings_requiring_value_apply(settings, effective_capabilities)


def _comparable_capabilities_for_request(
    capabilities: Mapping[str, JSONValue] | None,
    settings: JSONDict,
    *,
    device_entry: JSONDict | None,
    requested_field_modes: JSONDict,
) -> JSONDict | None:
    effective_capabilities = build_effective_capabilities(
        capabilities,
        current_field_modes=_effective_clock_modes_for_request(
            device_entry,
            settings,
            requested_field_modes,
        ),
        applied_settings=_entry_applied_settings(device_entry),
    )
    return _resolve_automatic_defaults(
        effective_capabilities,
        device_field_modes=read_device_field_modes(device_entry, settings),
    )


def _resolve_automatic_defaults(
    capabilities: JSONDict | None,
    *,
    device_field_modes: JSONDict,
) -> JSONDict | None:
    if capabilities is None:
        return None
    resolved: JSONDict = dict(capabilities)
    for descriptor in gpu_setting_descriptors():
        if device_field_modes.get(descriptor.request_key) != "auto":
            continue
        caps_entry = resolved.get(descriptor.caps_key)
        if not isinstance(caps_entry, dict):
            continue
        if coerce_gpu_setting_int(caps_entry.get("default"), round_float_strings=True) is not None:
            continue
        current_value = coerce_gpu_setting_int(
            caps_entry.get("current"),
            round_float_strings=True,
        )
        if current_value is None:
            continue
        next_entry = dict(caps_entry)
        next_entry["default"] = current_value
        resolved[descriptor.caps_key] = next_entry
    return resolved


def _entry_applied_settings(device_entry: JSONDict | None) -> JSONDict:
    if not isinstance(device_entry, dict):
        return {}
    raw_applied_settings = device_entry.get("applied_settings")
    return raw_applied_settings if isinstance(raw_applied_settings, dict) else {}


def _effective_clock_modes_for_request(
    device_entry: JSONDict | None,
    settings: JSONDict,
    requested_field_modes: JSONDict,
) -> JSONDict:
    current_modes = read_device_field_modes(device_entry, settings)
    effective_modes = dict(current_modes)
    for field in GPU_CLOCK_SETTING_FIELDS:
        if requested_field_modes.get(field) == "auto":
            effective_modes[field] = "auto"
    return effective_modes
