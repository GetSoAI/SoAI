"""SoAI - Hardware control GPU snapshot helpers [backend/hardware/control_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json_value import coerce_json_dict_or_empty, copy_json_dict
from core.validation.text_numbers import coerce_float_from_text
from hardware.gpu_capabilities.aggregate_payloads import (
    collect_control_backends,
    get_capabilities_for_device,
)
from hardware.gpu_capabilities.payloads import CONTROL_CAPABILITY_KEYS
from hardware.gpu_inventory.identity import normalize_identity_index

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_control_list_payload",
    "find_gpu_capabilities",
    "find_gpu_entry",
    "metric_float",
)


def find_gpu_entry(snapshot: JSONDict, device_id: str) -> JSONDict | None:
    gpu_payload = coerce_json_dict_or_empty(snapshot.get("gpu"))
    by_device = gpu_payload.get("by_device_id")
    if isinstance(by_device, Mapping):
        entry = by_device.get(device_id)
        if isinstance(entry, dict):
            return copy_json_dict(entry)
    gpus_value = gpu_payload.get("gpus")
    if isinstance(gpus_value, list):
        for entry in gpus_value:
            if isinstance(entry, dict) and entry.get("device_id") == device_id:
                return copy_json_dict(entry)
    return None


def find_gpu_capabilities(capabilities: JSONDict, gpu: JSONDict, device_id: str) -> JSONDict:
    gpu_index = normalize_identity_index(gpu.get("index"))
    cap_entry = get_capabilities_for_device(capabilities, device_id, gpu_index)
    if cap_entry is None:
        raise ValidationError(f"GPU capabilities are unavailable for {device_id}.")
    return cap_entry


def build_control_list_payload(snapshot: JSONDict, capabilities: JSONDict) -> JSONDict:
    gpu_payload = coerce_json_dict_or_empty(snapshot.get("gpu"))
    gpus_value = gpu_payload.get("gpus")
    supported: list[JSONDict] = []
    unsupported: list[JSONDict] = []
    if not isinstance(gpus_value, list):
        return {"supported_gpus": supported, "unsupported_gpus": unsupported}
    for gpu_value in gpus_value:
        if not isinstance(gpu_value, dict):
            continue
        gpu = copy_json_dict(gpu_value)
        device_id = gpu.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            continue
        cap_entry = get_capabilities_for_device(
            capabilities,
            device_id,
            normalize_identity_index(gpu.get("index")),
        )
        controls = _control_sections(cap_entry if isinstance(cap_entry, dict) else {})
        payload = {
            "device_id": device_id,
            "name": gpu.get("name"),
            "vendor": gpu.get("type") or gpu.get("vendor"),
            "gpu_index": gpu.get("index"),
            "backend_names": collect_control_backends(controls),
            "capabilities": controls,
            "current": gpu,
        }
        if any(section.get("supported") is True for section in controls.values()):
            supported.append(payload)
        else:
            payload["unsupported_reason"] = _unsupported_reason(controls)
            unsupported.append(payload)
    return {"supported_gpus": supported, "unsupported_gpus": unsupported}


def metric_float(entry: JSONDict, key: str) -> float | None:
    if key in entry:
        return coerce_float_from_text(entry.get(key), default=None)
    clock_value = entry.get("clock")
    if key == "core_clock_mhz" and isinstance(clock_value, Mapping):
        return coerce_float_from_text(clock_value.get("core_mhz"), default=None)
    if key == "mem_clock_mhz" and isinstance(clock_value, Mapping):
        return coerce_float_from_text(clock_value.get("memory_mhz"), default=None)
    return None


def _control_sections(capabilities: JSONDict) -> dict[str, JSONDict]:
    result: dict[str, JSONDict] = {}
    for key in CONTROL_CAPABILITY_KEYS:
        value = capabilities.get(key)
        result[key] = copy_json_dict(value) if isinstance(value, dict) else {}
    return result


def _unsupported_reason(controls: dict[str, JSONDict]) -> str:
    for section in controls.values():
        reason = section.get("unsupported_reason")
        if isinstance(reason, str) and reason:
            return reason
    return "unsupported_hardware"
