"""SoAI - Physical default-device selection for native runtimes [backend/core/hardware/native_execution_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.config.gpu_binding import GPU_BINDING_RUNTIME_CUDA, gpu_binding_selected_device_ids
from core.config.gpu_binding_devices import (
    resolve_gpu_binding_selected_entries,
    resolve_gpu_binding_visibility_tokens,
)
from core.errors.exceptions import ValidationError
from core.hardware.gpu_physical_identity import (
    GPUPhysicalBindingState,
    compare_gpu_physical_identities,
)
from core.hardware.gpu_physical_observations import read_gpu_physical_identity, read_gpu_vendor
from core.types.json import JSONDict, JSONValue

__all__ = (
    "resolve_native_runtime_default_device",
    "resolve_native_execution_devices",
    "native_execution_devices_unchanged",
)


def native_execution_devices_unchanged(
    initial: Mapping[str, JSONValue] | None,
    current: Mapping[str, JSONValue] | None,
    gpu_binding: JSONValue,
) -> bool:
    if initial is None or current is None:
        return False
    before = resolve_native_execution_devices(initial, gpu_binding)
    after = resolve_native_execution_devices(current, gpu_binding)
    if not before or not after or len(before) != len(after):
        return False
    current_by_id: dict[str, JSONDict] = {}
    for entry in after:
        device_id = entry.get("device_id")
        if not isinstance(device_id, str):
            return False
        current_by_id[device_id] = entry
    try:
        for entry in before:
            device_id = entry.get("device_id")
            if not isinstance(device_id, str):
                return False
            counterpart = current_by_id.get(device_id)
            if counterpart is None:
                return False
            expected = read_gpu_physical_identity(entry)
            observed = read_gpu_physical_identity(counterpart)
            if (
                expected is None
                or observed is None
                or compare_gpu_physical_identities(expected, observed)
                != GPUPhysicalBindingState.BOUND
            ):
                return False
        if gpu_binding_selected_device_ids(gpu_binding):
            return resolve_gpu_binding_visibility_tokens(
                before, GPU_BINDING_RUNTIME_CUDA
            ) == resolve_gpu_binding_visibility_tokens(after, GPU_BINDING_RUNTIME_CUDA)
    except ValidationError:
        return False
    return True


def resolve_native_execution_devices(
    inventory: Mapping[str, JSONValue], gpu_binding: JSONValue
) -> list[JSONDict] | None:
    devices: list[JSONDict]
    try:
        selected_ids = gpu_binding_selected_device_ids(gpu_binding)
        if selected_ids:
            devices = resolve_gpu_binding_selected_entries(inventory, selected_ids)
            return devices if _native_execution_observations_consistent(devices) else None
    except ValidationError:
        return None
    payload = inventory.get("gpu")
    entries = payload.get("gpus") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return None
    try:
        devices = []
        for entry in entries:
            if not isinstance(entry, dict):
                return None
            vendor = read_gpu_vendor(entry)
            if vendor is None or vendor.casefold() == "unknown":
                return None
            if vendor.casefold() == "nvidia":
                devices.append(dict(entry))
    except ValidationError:
        return None
    return devices if _native_execution_observations_consistent(devices) else None


def _native_execution_observations_consistent(devices: list[JSONDict]) -> bool:
    identities = [entry.get("device_id") for entry in devices]
    if any(
        not isinstance(identity, str) or not identity or identity != identity.strip()
        for identity in identities
    ):
        return False
    if len({identity for identity in identities if isinstance(identity, str)}) != len(devices):
        return False
    try:
        physical = [read_gpu_physical_identity(entry) for entry in devices]
        return not any(
            first is not None
            and second is not None
            and compare_gpu_physical_identities(first, second)
            in (GPUPhysicalBindingState.BOUND, GPUPhysicalBindingState.IDENTITY_CONFLICT)
            for index, first in enumerate(physical)
            for second in physical[index + 1 :]
        )
    except ValidationError:
        return False


def resolve_native_runtime_default_device(
    devices: list[JSONDict],
    *,
    explicitly_selected: bool,
    runtime_device: Mapping[str, JSONValue] | None,
) -> list[JSONDict] | None:
    try:
        expected = None
        if explicitly_selected:
            visibility = resolve_gpu_binding_visibility_tokens(devices, GPU_BINDING_RUNTIME_CUDA)
            if not visibility.uses_numeric_indices:
                identities = [read_gpu_physical_identity(device) for device in devices]
                if any(identity is None for identity in identities):
                    return None
                if len({token.casefold() for token in visibility.values}) != len(devices):
                    return None
                expected = devices[0]
        if runtime_device is None:
            return [expected] if expected is not None else None
        if runtime_device.get("type") != "nvidia":
            return None
        observed_identity = read_gpu_physical_identity(dict(runtime_device))
        if observed_identity is None:
            return None
        matches: list[JSONDict] = []
        for device in devices:
            identity = read_gpu_physical_identity(device)
            if identity is None:
                return None
            comparison = compare_gpu_physical_identities(observed_identity, identity)
            if comparison == GPUPhysicalBindingState.IDENTITY_CONFLICT:
                return None
            if comparison == GPUPhysicalBindingState.BOUND:
                matches.append(device)
        if len(matches) != 1 or (expected is not None and matches[0] != expected):
            return None
        return matches
    except ValidationError:
        return None
