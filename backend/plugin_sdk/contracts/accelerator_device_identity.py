"""SoAI - Plugin SDK accelerator device identity parsing [backend/plugin_sdk/contracts/accelerator_device_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.hardware.gpu_identity_normalization import normalize_identity_name, normalize_pci_bdf
from core.types.json import JSONDict, JSONValue

__all__ = (
    "accelerator_field_value",
    "accelerator_string_field",
    "normalize_accelerator_hex_id",
    "normalize_accelerator_identity",
    "optional_accelerator_pci_bdf",
)


def accelerator_field_value(payload: JSONDict, keys: tuple[str, ...]) -> JSONValue:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def accelerator_string_field(payload: JSONDict, keys: tuple[str, ...]) -> str | None:
    value = accelerator_field_value(payload, keys)
    return value.strip() if isinstance(value, str) and value.strip() else None


def normalize_accelerator_hex_id(value: JSONValue) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return f"{value:x}"
    if isinstance(value, str) and value.strip():
        cleaned = value.strip().lower()
        if cleaned.startswith("0x"):
            cleaned = cleaned[2:]
        cleaned = re.sub(r"[^0-9a-f]", "", cleaned)
        return cleaned or None
    return None


def normalize_accelerator_identity(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_identity_name(value)
    return normalized or None


def optional_accelerator_pci_bdf(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_pci_bdf(value)
    return normalized or None
