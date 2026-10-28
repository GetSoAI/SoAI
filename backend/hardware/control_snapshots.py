"""SoAI - Hardware control GPU snapshot helpers [backend/hardware/control_snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.types.json_value import coerce_json_dict_or_empty, copy_json_dict
from hardware.gpu_capabilities.aggregate_payloads import (
    collect_control_backends,
    get_capabilities_for_device,
)
from hardware.gpu_capabilities.payloads import CONTROL_CAPABILITY_KEYS
from hardware.gpu_inventory.identity import normalize_identity_index
from hardware.gpu_inventory.physical_binding import (
    gpu_entry_accepts_device_id,
    match_gpu_physical_identity,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_control_list_payload",
    "find_gpu_capabilities",
    "find_gpu_entry",
)


def find_gpu_entry(snapshot: JSONDict, device_id: str) -> JSONDict | None:
    gpu_payload = coerce_json_dict_or_empty(snapshot.get("gpu"))
    by_device = gpu_payload.get("by_device_id")
    mapped = by_device.get(device_id) if isinstance(by_device, Mapping) else None
    gpus_value = gpu_payload.get("gpus")
    entries: list[JSONDict]
    if isinstance(gpus_value, list):
        entries = [entry for entry in gpus_value if isinstance(entry, dict)]
    elif isinstance(by_device, Mapping):
        entries = []
        for entry in by_device.values():
            if isinstance(entry, dict) and entry not in entries:
                entries.append(entry)
    else:
        return None
    matches = [entry for entry in entries if entry.get("device_id") == device_id]
    if not matches:
        matches = [entry for entry in entries if gpu_entry_accepts_device_id(entry, device_id)]
    if len(matches) != 1:
        return None
    selected = matches[0]
    if isinstance(mapped, dict) and not _snapshot_identity_agrees(selected, mapped):
        return None
    return copy_json_dict(selected)


def _snapshot_identity_agrees(selected: JSONDict, mapped: JSONDict) -> bool:
    mapped_id = mapped.get("device_id")
    if not isinstance(mapped_id, str) or not gpu_entry_accepts_device_id(selected, mapped_id):
        return False
    relation = match_gpu_physical_identity(selected, mapped)
    if relation == GPUPhysicalBindingState.BOUND:
        return True
    if relation != GPUPhysicalBindingState.IDENTITY_UNAVAILABLE:
        return False
    if mapped_id != selected.get("device_id"):
        return False
    selected_index = normalize_identity_index(selected.get("index"))
    mapped_index = normalize_identity_index(mapped.get("index"))
    return selected_index is None or mapped_index is None or selected_index == mapped_index


def find_gpu_capabilities(capabilities: JSONDict, gpu: JSONDict, device_id: str) -> JSONDict:
    gpu_index = normalize_identity_index(gpu.get("index"))
    cap_entry = get_capabilities_for_device(capabilities, device_id, gpu_index, selected_gpu=gpu)
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
            selected_gpu=gpu,
        )
        controls = _control_sections(cap_entry if isinstance(cap_entry, dict) else {})
        binding_state = gpu.get("control_binding_state")
        reason = gpu.get("control_binding_reason")
        if find_gpu_entry(snapshot, device_id) is None:
            binding_state, reason = GPUPhysicalBindingState.IDENTITY_CONFLICT, "identity_conflict"
        if binding_state is not None and binding_state != GPUPhysicalBindingState.BOUND:
            for section in controls.values():
                section["supported"] = False
                section["unsupported_reason"] = reason or binding_state
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
