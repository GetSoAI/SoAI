"""SoAI - Aggregate GPU capability payload helpers [backend/hardware/gpu_capabilities/aggregate_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.payload import ErrorPublicPayload
from hardware.gpu_capabilities.payloads import (
    CONTROL_CAPABILITY_KEYS,
    read_control_capability_section,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_capabilities_aggregate_payload",
    "build_probe_error_payload",
    "collect_control_backends",
    "get_capabilities_for_device",
    "merge_capabilities_into_gpu_snapshot",
)


def build_capabilities_aggregate_payload(
    *,
    compute_drivers: JSONDict,
    total_vram_gb: float,
) -> JSONDict:
    return {
        "success": True,
        "gpus": {},
        "gpus_by_device_id": {},
        "compute_drivers": compute_drivers,
        "total_vram_gb": total_vram_gb,
    }


def build_probe_error_payload(error_type: str, message: str) -> JSONDict:
    return {
        "success": False,
        "gpus": {},
        "gpus_by_device_id": {},
        "compute_drivers": {},
        "total_vram_gb": 0,
        "error": ErrorPublicPayload(code=error_type, message=message).to_dict(),
    }


def collect_control_backends(caps: Mapping[str, JSONValue]) -> list[str]:
    backends: list[str] = []
    for caps_key in CONTROL_CAPABILITY_KEYS:
        cap_entry = read_control_capability_section(caps, caps_key)
        backend = cap_entry.get("control_backend")
        if isinstance(backend, str) and backend and backend not in backends:
            backends.append(backend)
    return backends


def get_capabilities_for_device(
    capabilities: JSONDict,
    device_id: str | None,
    gpu_index: int | None,
) -> JSONDict | None:
    by_device = capabilities.get("gpus_by_device_id") if isinstance(capabilities, dict) else None
    if isinstance(by_device, dict) and device_id and (device_id in by_device):
        entry = by_device[device_id]
        return entry if isinstance(entry, dict) else None
    by_index = capabilities.get("gpus") if isinstance(capabilities, dict) else None
    if isinstance(by_index, dict) and (gpu_index is not None):
        index_key = str(gpu_index)
        if index_key in by_index:
            entry = by_index[index_key]
            return entry if isinstance(entry, dict) else None
    return None


def merge_capabilities_into_gpu_snapshot(gpu_snapshot: JSONDict, capabilities: JSONDict) -> None:
    caps_by_index = capabilities.get("gpus")
    gpus_value = gpu_snapshot.get("gpus")
    if not isinstance(caps_by_index, dict) or not isinstance(gpus_value, list):
        return
    for gpu_data in gpus_value:
        if not isinstance(gpu_data, dict):
            continue
        gpu_index = gpu_data.get("index")
        if not isinstance(gpu_index, int):
            continue
        index_key = str(gpu_index)
        caps_entry = caps_by_index.get(index_key)
        if not isinstance(caps_entry, dict):
            continue
        for key, value in caps_entry.items():
            if key not in gpu_data:
                gpu_data[key] = value
