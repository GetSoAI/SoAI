"""SoAI - GPU inventory payload shaping [backend/hardware/gpu_inventory/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Sequence

from core.config.gpu_binding_devices import is_gpu_binding_eligible_entry
from core.hardware.device_display_name import build_device_display_name
from core.types.json import JSONDict

__all__ = (
    "build_gpu_payload",
    "simplify_gpu_payload",
)


def _apply_display_names(gpus: list[JSONDict]) -> None:
    for entry in gpus:
        entry["display_name"] = build_device_display_name(entry.get("name"))


def _build_by_device_id(gpus: list[JSONDict]) -> dict[str, JSONDict]:
    by_device_id: dict[str, JSONDict] = {}
    for entry in gpus:
        device_id_value = entry.get("device_id")
        if isinstance(device_id_value, str) and device_id_value:
            by_device_id[device_id_value] = entry
    return by_device_id


def _binding_device(entry: JSONDict) -> JSONDict | None:
    device_id = entry.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return None
    payload: JSONDict = {
        "device_id": device_id,
        "label": entry.get("name") if isinstance(entry.get("name"), str) else device_id,
        "vendor": entry.get("type") if isinstance(entry.get("type"), str) else "unknown",
        "index": entry.get("index"),
        "binding_index": entry.get("vendor_id"),
        "memory_total_mb": entry.get("memory_total_mb"),
    }
    for key in ("gpu_uuid", "pci_bdf", "pci_vendor_id", "pci_device_id"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value
    return payload


def _build_binding_payload(gpus: list[JSONDict]) -> JSONDict:
    devices: list[JSONDict] = []
    for entry in gpus:
        if not is_gpu_binding_eligible_entry(entry):
            continue
        device = _binding_device(entry)
        if device is not None:
            devices.append(device)
    return {
        "devices": devices,
        "default": {"mode": "all", "device_ids": []},
    }


def build_gpu_payload(
    gpus: list[JSONDict],
    drivers: JSONDict,
    display_adapters: Sequence[JSONDict] = (),
) -> JSONDict:
    gpus_copy = [copy.deepcopy(entry) for entry in gpus]
    _apply_display_names(gpus_copy)
    drivers_copy = copy.deepcopy(drivers)
    return {
        "gpus": gpus_copy,
        "compute_drivers": drivers_copy,
        "by_device_id": _build_by_device_id(gpus_copy),
        "display_adapters": [copy.deepcopy(entry) for entry in display_adapters],
        "binding": _build_binding_payload(gpus_copy),
    }


def simplify_gpu_payload(payload: JSONDict) -> JSONDict:
    simplified_gpus: list[JSONDict] = []
    gpus_value = payload.get("gpus", [])
    if isinstance(gpus_value, list):
        for entry in gpus_value:
            if isinstance(entry, dict):
                clone = copy.deepcopy(entry)
                clone["processes"] = []
                simplified_gpus.append(clone)
    drivers_value = payload.get("compute_drivers", {})
    drivers_copy = copy.deepcopy(drivers_value) if isinstance(drivers_value, dict) else {}
    adapters_value = payload.get("display_adapters", [])
    adapters_copy = (
        [copy.deepcopy(entry) for entry in adapters_value if isinstance(entry, dict)]
        if isinstance(adapters_value, list)
        else []
    )
    return {
        "gpus": simplified_gpus,
        "compute_drivers": drivers_copy,
        "by_device_id": _build_by_device_id(simplified_gpus),
        "display_adapters": adapters_copy,
        "binding": _build_binding_payload(simplified_gpus),
    }
