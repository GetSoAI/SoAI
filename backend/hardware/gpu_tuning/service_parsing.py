"""SoAI - Parsing helpers for GPU tuning service [backend/hardware/gpu_tuning/service_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.validation.coercion import coerce_int_from_scalar
from core.validation.numbers import coerce_int_from_json
from hardware.gpu_inventory.identity import normalize_gpu_index

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_auto_or_gpu_setting_int",
    "coerce_gpu_setting_int",
    "coerce_gpu_setting_int_for_apply",
    "is_auto_gpu_setting",
    "prepare_settings_payload",
    "read_capability_setting_int",
)


def is_auto_gpu_setting(value: JSONValue) -> bool:
    return isinstance(value, str) and value.lower() == "auto"


def coerce_auto_or_gpu_setting_int(value: JSONValue) -> tuple[bool, int | None]:
    if is_auto_gpu_setting(value):
        return (True, None)
    return (False, coerce_int_from_scalar(value))


def coerce_gpu_setting_int(value: JSONValue, *, round_float_strings: bool = False) -> int | None:
    return coerce_int_from_json(
        value,
        default=None,
        parse_float_strings=True,
        round_float_strings=round_float_strings,
    )


def coerce_gpu_setting_int_for_apply(value: JSONValue, label: str, errors: list[str]) -> int | None:
    parsed = coerce_gpu_setting_int(value)
    if parsed is not None:
        return parsed
    if isinstance(value, bool):
        errors.append(f"{label} must be a number, got {type(value).__name__}")
    elif isinstance(value, str) and not value.strip():
        errors.append(f"{label} must be a non-empty number string.")
    elif isinstance(value, str):
        errors.append(f"{label} must be a number, got {value!r}")
    else:
        errors.append(f"{label} must be a number, got {type(value).__name__}")
    return None


def read_capability_setting_int(capabilities: JSONDict, key: str) -> int | None:
    raw_entry = capabilities.get(key)
    if not isinstance(raw_entry, dict):
        return None
    return coerce_gpu_setting_int(raw_entry.get("default"))


def prepare_settings_payload(
    settings_payload: JSONDict,
) -> tuple[int | None, dict[str, JSONValue]]:
    gpu_id = normalize_gpu_index(settings_payload.get("gpu_id"))
    cleaned = {key: value for key, value in settings_payload.items() if key != "gpu_id"}
    return gpu_id, cleaned
