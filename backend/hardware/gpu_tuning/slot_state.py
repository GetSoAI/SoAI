"""SoAI - GPU slot live state calculation [backend/hardware/gpu_tuning/slot_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.hardware.gpu_settings_contract import GPU_CLOCK_SETTING_FIELDS
from core.logging.trace import get_logger
from core.validation.numbers import coerce_int_from_json
from hardware.gpu_tuning.boot_state import boot_enabled, boot_payload_from_value
from hardware.gpu_tuning.direct_control_state import (
    applied_settings_from_sanitized,
    control_state_matches,
)
from hardware.gpu_tuning.effective_control_state import (
    build_apply_settings_for_modes,
    build_effective_capabilities,
    settings_values_match_effective,
)
from hardware.gpu_tuning.setting_capabilities import (
    capability_supported,
    gpu_setting_descriptors,
)
from hardware.gpu_tuning.setting_modes import (
    field_modes_mapping_or_none,
    normalize_field_mode,
    normalize_field_mode_mapping,
    normalize_field_modes_for_settings,
    read_device_field_modes,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_live_state",
    "extract_current_settings",
)

LOGGER_NAME = "SoAI.hardware.gpu_tuning.slot_state"
OPERATION_COERCE_BOOL_FLAG = "hardware.gpu_tuning.slot_state.coerce_bool_flag"


def extract_current_settings(
    capabilities: JSONDict | None,
    *,
    field_modes: Mapping[str, JSONValue] | None = None,
    applied_settings: Mapping[str, JSONValue] | None = None,
) -> JSONDict:
    if not isinstance(capabilities, dict):
        return {}
    normalize = coerce_int_from_json

    def resolve_mode(key: str) -> str | None:
        if not isinstance(field_modes, Mapping):
            return None
        return normalize_field_mode(field_modes.get(key))

    def resolve_applied_value(key: str) -> int | None:
        if not isinstance(applied_settings, Mapping):
            return None
        return normalize(applied_settings.get(key))

    def build_entry(current: JSONValue, default: JSONValue, key: str) -> JSONDict | None:
        if (current_value := normalize(current)) is None:
            applied_value = resolve_applied_value(key)
            if applied_value is None:
                return None
            current_value = applied_value
        entry: JSONDict = {"value": current_value}
        default_value = normalize(default)
        if default_value is not None:
            entry["default"] = default_value
        mode = resolve_mode(key)
        applied_value = resolve_applied_value(key)
        if mode == "manual" and applied_value is not None:
            if key in GPU_CLOCK_SETTING_FIELDS:
                entry["value"] = applied_value
            entry["is_default"] = False
            return entry
        if mode == "auto":
            entry["is_default"] = True
        elif mode == "manual":
            entry["is_default"] = False
        elif default_value is not None:
            entry["is_default"] = current_value == default_value
        return entry

    result: JSONDict = {}
    for descriptor in gpu_setting_descriptors():
        caps_entry = capabilities.get(descriptor.caps_key)
        if not isinstance(caps_entry, dict):
            continue
        if not capability_supported(
            caps_entry.get("supported"),
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION_COERCE_BOOL_FLAG,
            recover_message="Failed to parse boolean flag (non-critical).",
        ):
            continue
        state_entry = build_entry(
            caps_entry.get("current"),
            caps_entry.get("default"),
            descriptor.request_key,
        )
        if state_entry is not None:
            result[descriptor.request_key] = state_entry
    return result


def build_live_state(
    device_id: str,
    entry: JSONDict | None,
    capabilities: JSONDict | None,
) -> JSONDict:
    live: JSONDict = {"device_id": device_id}
    raw_modes = entry.get("field_modes") if isinstance(entry, dict) else None
    field_modes = normalize_field_mode_mapping(raw_modes)
    raw_applied_settings = entry.get("applied_settings") if isinstance(entry, dict) else None
    applied_settings = raw_applied_settings if isinstance(raw_applied_settings, dict) else {}
    current_settings = (
        extract_current_settings(
            capabilities,
            field_modes=field_modes,
            applied_settings=applied_settings,
        )
        or {}
    )
    live["current_settings"] = current_settings
    effective_capabilities = build_effective_capabilities(
        capabilities,
        current_field_modes=field_modes,
        applied_settings=applied_settings,
    )
    raw_boot = entry.get("boot") if isinstance(entry, dict) else None
    boot_payload = boot_payload_from_value(raw_boot)
    enabled = boot_enabled(
        boot_payload,
        logger=get_logger(LOGGER_NAME),
        operation="hardware.gpu_tuning.slot_state.coerce_bool_flag",
    )
    live["boot_state"], live["boot_enabled"] = (boot_payload, enabled)
    live["boot_slot"] = boot_payload.get("slot") if enabled else None
    active_slot, active_signature, active_applied_at = (None, None, None)
    if isinstance(entry, dict) and isinstance((slots := entry.get("slots", {})), dict):
        for slot_id, slot_entry in slots.items():
            if not (
                isinstance(slot_entry, dict)
                and isinstance((settings := slot_entry.get("settings")), dict)
            ):
                continue
            requested_field_modes = field_modes_mapping_or_none(slot_entry.get("field_modes"))
            normalized_requested_modes = normalize_field_modes_for_settings(
                settings,
                requested_field_modes,
            )
            requested_applied_settings = applied_settings_from_sanitized(
                settings,
                normalized_requested_modes,
            )
            current_field_modes = read_device_field_modes(entry, settings)
            device_entry: JSONDict = {
                "field_modes": current_field_modes,
                "applied_settings": applied_settings,
            }
            apply_settings = build_apply_settings_for_modes(
                settings,
                normalized_requested_modes,
            )
            if control_state_matches(
                device_entry=device_entry,
                requested_settings=settings,
                requested_field_modes=normalized_requested_modes,
                requested_applied_settings=requested_applied_settings,
            ) and settings_values_match_effective(
                apply_settings,
                effective_capabilities,
                device_entry=device_entry,
                requested_field_modes=normalized_requested_modes,
            ):
                active_slot, active_signature, active_applied_at = (
                    slot_id,
                    slot_entry.get("signature"),
                    slot_entry.get("last_applied_at"),
                )
                break
    live["active_slot"], live["active_signature"], live["active_applied_at"] = (
        active_slot,
        active_signature,
        active_applied_at,
    )
    return live
