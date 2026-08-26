"""SoAI - GPU inventory identity normalization [backend/hardware/gpu_inventory/identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.hardware.gpu_identity_normalization import (
    normalize_identity_name,
    normalize_model_key,
    normalize_pci_bdf,
)
from core.types.json_value import coerce_json_dict_or_empty
from core.validation.numbers import coerce_int_from_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "normalize_gpu_index",
    "normalize_identity_index",
    "normalize_identity_name",
    "normalize_model_key",
    "normalize_pci_bdf",
    "normalize_uuid",
    "optional_identity_text",
    "snapshot_gpu_entries",
    "uuid_from_device_id",
    "windows_adapter_primary_device_id",
)


def optional_identity_text(value: JSONValue) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def normalize_gpu_index(value: JSONValue) -> int | None:
    return coerce_int_from_json(value, default=None)


def normalize_identity_index(value: JSONValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def normalize_uuid(value: str) -> str:
    normalized = normalize_identity_name(value)
    if normalized.startswith("gpu") and len(normalized) > 32:
        normalized = normalized[3:]
    return normalized


def uuid_from_device_id(device_id: str | None) -> str | None:
    if device_id is None:
        return None
    prefix = "gpu:nvidia-gpu-"
    if device_id.startswith(prefix):
        suffix = device_id.removeprefix(prefix)
        return f"GPU-{suffix}" if suffix else None
    return None


def snapshot_gpu_entries(snapshot: JSONDict) -> list[JSONDict]:
    gpu_payload = coerce_json_dict_or_empty(snapshot.get("gpu"))
    entries: list[JSONDict] = []
    device_ids: list[str] = []
    gpus_value = gpu_payload.get("gpus")
    if isinstance(gpus_value, list):
        for entry in gpus_value:
            if isinstance(entry, dict):
                _append_snapshot_gpu_entry(entries, device_ids, entry)
    by_device = gpu_payload.get("by_device_id")
    if isinstance(by_device, Mapping):
        for entry in by_device.values():
            if isinstance(entry, dict):
                _append_snapshot_gpu_entry(entries, device_ids, entry)
    return entries


def windows_adapter_primary_device_id(gpu_info: JSONDict, vendor: str) -> str | None:
    for key in ("PNPDeviceID", "DeviceID"):
        value = gpu_info.get(key)
        if value:
            return f"{vendor}-{value}"
    return None


def _append_snapshot_gpu_entry(
    entries: list[JSONDict],
    device_ids: list[str],
    entry: JSONDict,
) -> None:
    device_id = optional_identity_text(entry.get("device_id"))
    if device_id is not None:
        if device_id in device_ids:
            return
        device_ids.append(device_id)
    entries.append(entry)
