"""SoAI - GPU capabilities with scalar snapshot metrics and resource-owned control descriptors [backend/hardware/gpu_capabilities/aggregate_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.payload import ErrorPublicPayload
from core.hardware.gpu_physical_identity import GPUPhysicalBindingState
from core.hardware.gpu_physical_observations import read_gpu_physical_identity
from core.validation.strings import coerce_optional_trimmed_str
from hardware.gpu_capabilities.payloads import (
    CONTROL_CAPABILITY_KEYS,
    mark_all_control_capabilities_unsupported,
    read_control_capability_section,
)
from hardware.gpu_inventory.identity import normalize_identity_index, uuid_from_device_id
from hardware.gpu_inventory.physical_binding import (
    gpu_entry_accepts_device_id,
    match_gpu_physical_identity,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_capabilities_aggregate_payload",
    "build_probe_error_payload",
    "collect_control_backends",
    "get_capabilities_for_device",
    "merge_capabilities_into_gpu_snapshot",
    "project_inventory_capability_identity",
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
    *,
    selected_gpu: JSONDict | None = None,
) -> JSONDict | None:
    if (
        selected_gpu is not None
        and device_id
        and not gpu_entry_accepts_device_id(selected_gpu, device_id)
    ):
        return None
    by_device = capabilities.get("gpus_by_device_id") if isinstance(capabilities, dict) else None
    device_keys = [device_id] if device_id else []
    canonical_id = selected_gpu.get("device_id") if selected_gpu is not None else None
    if isinstance(canonical_id, str) and canonical_id not in device_keys:
        device_keys.append(canonical_id)
    if isinstance(by_device, dict):
        for device_key in device_keys:
            if device_key in by_device:
                entry = by_device[device_key]
                return (
                    entry
                    if isinstance(entry, dict)
                    and _capability_identity_agrees(entry, device_id, selected_gpu, indexed=False)
                    else None
                )
        if device_id:
            aliases = [
                entry
                for entry in by_device.values()
                if isinstance(entry, dict) and gpu_entry_accepts_device_id(entry, device_id)
            ]
            if aliases:
                return (
                    aliases[0]
                    if len(aliases) == 1
                    and _capability_identity_agrees(
                        aliases[0], device_id, selected_gpu, indexed=False
                    )
                    else None
                )
    by_index = capabilities.get("gpus") if isinstance(capabilities, dict) else None
    if isinstance(by_index, dict) and (gpu_index is not None):
        index_key = str(gpu_index)
        if index_key in by_index:
            entry = by_index[index_key]
            return (
                entry
                if isinstance(entry, dict)
                and _capability_identity_agrees(entry, device_id, selected_gpu, indexed=True)
                else None
            )
    return None


def _capability_identity_agrees(
    entry: JSONDict,
    device_id: str | None,
    selected_gpu: JSONDict | None,
    *,
    indexed: bool,
) -> bool:
    if entry.get("device_id") is not None and not isinstance(entry.get("device_id"), str):
        return False
    entry_id = coerce_optional_trimmed_str(entry.get("device_id"))
    if device_id is not None:
        if selected_gpu is not None:
            if entry_id is not None and not gpu_entry_accepts_device_id(selected_gpu, entry_id):
                return False
        else:
            if (
                entry_id is not None
                and entry_id != device_id
                and not gpu_entry_accepts_device_id(entry, device_id)
            ):
                return False
            if indexed and entry_id != device_id:
                return False
    if entry.get("control_binding_state") in (
        GPUPhysicalBindingState.IDENTITY_CONFLICT,
        GPUPhysicalBindingState.INVALID_RESPONSE,
    ):
        return False
    observations = [entry]
    inventory_identity = entry.get("inventory_physical_identity")
    if inventory_identity is not None:
        if (
            not isinstance(inventory_identity, dict)
            or not {"uuid", "pci_bdf_full"} <= set(inventory_identity)
            or set(inventory_identity)
            - {"uuid", "pci_bdf_full", "windows_pnp_instance_id", "native_device_path"}
        ):
            return False
        inventory_observation: JSONDict = {
            "gpu_uuid": inventory_identity["uuid"],
            "pci_bdf_full": inventory_identity["pci_bdf_full"],
            "type": entry.get("type"),
            "vendor": entry.get("vendor"),
        }
        if "windows_pnp_instance_id" in inventory_identity:
            pnp_instance = inventory_identity["windows_pnp_instance_id"]
            if not isinstance(pnp_instance, str) or not pnp_instance:
                return False
            inventory_observation["windows_pnp_instance_id"] = pnp_instance
        if "native_device_path" in inventory_identity:
            native_path = inventory_identity["native_device_path"]
            if not isinstance(native_path, str) or not native_path:
                return False
            inventory_observation["native_device_path"] = native_path
        observations.append(inventory_observation)
    expected: JSONDict | None = selected_gpu
    if expected is None:
        requested_uuid = uuid_from_device_id(device_id)
        if requested_uuid is not None:
            expected = {"gpu_uuid": requested_uuid, "type": "nvidia"}
    if expected is not None:
        if expected.get("control_binding_state") in (
            GPUPhysicalBindingState.IDENTITY_CONFLICT,
            GPUPhysicalBindingState.INVALID_RESPONSE,
        ):
            return False
        observations.append(expected)
    try:
        for observation in observations:
            read_gpu_physical_identity(observation)
    except ValidationError:
        return False
    for index, observation in enumerate(observations):
        for other in observations[index + 1 :]:
            relation = match_gpu_physical_identity(observation, other)
            if relation in (
                GPUPhysicalBindingState.IDENTITY_CONFLICT,
                GPUPhysicalBindingState.DEVICE_UNAVAILABLE,
                GPUPhysicalBindingState.INVALID_RESPONSE,
            ):
                return False
    if indexed and device_id is not None:
        if expected is None or not any(
            match_gpu_physical_identity(expected, observation) == GPUPhysicalBindingState.BOUND
            for observation in observations
            if observation is not expected
        ):
            return False
    return True


def merge_capabilities_into_gpu_snapshot(gpu_snapshot: JSONDict, capabilities: JSONDict) -> None:
    gpus_value = gpu_snapshot.get("gpus")
    if not isinstance(gpus_value, list):
        return
    for gpu_data in gpus_value:
        if not isinstance(gpu_data, dict):
            continue
        gpu_index = normalize_identity_index(gpu_data.get("index"))
        device_id = coerce_optional_trimmed_str(gpu_data.get("device_id"))
        if device_id is None:
            continue
        caps_entry = get_capabilities_for_device(
            capabilities, device_id, gpu_index, selected_gpu=gpu_data
        )
        if not isinstance(caps_entry, dict):
            continue
        for key, value in caps_entry.items():
            if key in CONTROL_CAPABILITY_KEYS:
                continue
            if key not in gpu_data:
                gpu_data[key] = copy.deepcopy(value)


def project_inventory_capability_identity(gpu: JSONDict, caps_payload: JSONDict) -> JSONDict:
    caps_copy = copy.deepcopy(caps_payload)
    try:
        inventory_identity = read_gpu_physical_identity(gpu)
    except ValidationError:
        inventory_identity = None
        relation = GPUPhysicalBindingState.INVALID_RESPONSE
    else:
        relation = match_gpu_physical_identity(gpu, caps_payload)
    if inventory_identity is not None:
        observed_identity: JSONDict = {
            "uuid": inventory_identity.uuid,
            "pci_bdf_full": inventory_identity.pci_bdf_full,
        }
        if inventory_identity.windows_pnp_instance_id is not None:
            observed_identity["windows_pnp_instance_id"] = (
                inventory_identity.windows_pnp_instance_id
            )
        if inventory_identity.native_device_path is not None:
            observed_identity["native_device_path"] = inventory_identity.native_device_path
        caps_copy["inventory_physical_identity"] = observed_identity
    for field in ("control_binding_state", "control_binding_reason", "device_id_aliases"):
        if (
            field != "device_id_aliases"
            and relation == GPUPhysicalBindingState.BOUND
            and caps_payload.get("control_binding_state") == GPUPhysicalBindingState.BOUND
            and gpu.get("control_binding_state") == GPUPhysicalBindingState.QUERY_UNAVAILABLE
        ):
            continue
        if field in gpu:
            caps_copy[field] = copy.deepcopy(gpu[field])
    observed_id = caps_payload.get("device_id")
    if observed_id is not None and (
        not isinstance(observed_id, str) or not gpu_entry_accepts_device_id(gpu, observed_id)
    ):
        relation = GPUPhysicalBindingState.IDENTITY_CONFLICT
    if relation in (
        GPUPhysicalBindingState.IDENTITY_CONFLICT,
        GPUPhysicalBindingState.DEVICE_UNAVAILABLE,
        GPUPhysicalBindingState.INVALID_RESPONSE,
    ):
        state = (
            GPUPhysicalBindingState.INVALID_RESPONSE
            if relation == GPUPhysicalBindingState.INVALID_RESPONSE
            else GPUPhysicalBindingState.IDENTITY_CONFLICT
        )
        caps_copy["control_binding_state"] = state.value
        caps_copy["control_binding_reason"] = "native_identity_conflict"
        mark_all_control_capabilities_unsupported(caps_copy, "native_identity_conflict", force=True)
    return caps_copy
