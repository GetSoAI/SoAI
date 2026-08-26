"""SoAI - GPU settings validation utilities [backend/hardware/validate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import (
    GPU_CLOCK_SETTING_FIELDS,
    GPU_RANGED_SETTING_FIELDS,
    GPU_RESET_CLOCKS_FIELD,
    GPU_SETTING_FIELDS,
)
from core.logging.trace import get_logger
from core.validation.booleans import parse_bool
from hardware.gpu_tuning.setting_capabilities import (
    get_capability_entry,
    sanitize_ranged_setting,
    setting_descriptor_for_key,
)
from hardware.validate_current_match import settings_match_current

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sanitize_ranged_setting",
    "sanitize_settings",
    "settings_match_current",
)

LOGGER_NAME = "SoAI.hardware.validate"
OPERATION = "hardware.validate.sanitize_settings.is_supported_flag"


def sanitize_settings(settings: JSONDict, capabilities: JSONDict | None) -> JSONDict:
    if not isinstance(settings, dict) or not settings:
        raise ValidationError("GPU settings payload must be a non-empty object.")
    sanitized: JSONDict = {}
    caps = capabilities or {}
    for raw_key in settings:
        if raw_key not in GPU_SETTING_FIELDS and raw_key not in ("gpu_id", "device_id"):
            raise ValidationError(f"Unsupported GPU setting key '{raw_key}'.")
    for key in GPU_RANGED_SETTING_FIELDS:
        if key not in settings:
            continue
        descriptor = setting_descriptor_for_key(key)
        if descriptor is None:
            continue
        caps_entry = get_capability_entry(
            caps,
            descriptor,
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION,
        )
        sanitized[key] = sanitize_ranged_setting(descriptor, settings[key], caps_entry)
    reset_flag = parse_bool(settings.get(GPU_RESET_CLOCKS_FIELD), default=False)
    if reset_flag:
        sanitized[GPU_RESET_CLOCKS_FIELD] = True
    if any(key in settings for key in GPU_CLOCK_SETTING_FIELDS):
        if reset_flag:
            raise ValidationError(
                "Cannot provide OverDrive values when reset_clocks is enabled.",
            )
        for key in GPU_CLOCK_SETTING_FIELDS:
            if key not in settings:
                continue
            descriptor = setting_descriptor_for_key(key)
            if descriptor is None:
                continue
            caps_entry = get_capability_entry(
                caps,
                descriptor,
                logger=get_logger(LOGGER_NAME),
                operation=OPERATION,
            )
            sanitized[key] = sanitize_ranged_setting(
                descriptor,
                settings[key],
                caps_entry,
            )
    if not sanitized:
        raise ValidationError("No supported GPU settings were provided.")
    return sanitized
