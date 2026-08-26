"""SoAI - Hardware control request parsing contracts [backend/core/hardware/control_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_settings_contract import GPU_SETTING_FIELDS
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "parse_required_device_id",
    "parse_settings",
)


def parse_required_device_id(arguments: JSONDict) -> str:
    if not isinstance(arguments, Mapping):
        raise ValidationError("device_id is required.")
    value = arguments.get("device_id")
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("device_id is required.")
    return value.strip()


def parse_settings(arguments: JSONDict) -> JSONDict:
    if not isinstance(arguments, Mapping):
        raise ValidationError("settings must be a non-empty object.")
    value = coerce_json_dict(arguments.get("settings"))
    if value is None or not value:
        raise ValidationError("settings must be a non-empty object.")
    settings: JSONDict = {}
    for key, item in value.items():
        if key not in GPU_SETTING_FIELDS:
            raise ValidationError(f"Unsupported GPU setting key '{key}'.")
        settings[key] = item
    if not settings:
        raise ValidationError("settings must include at least one supported setting.")
    return settings
