"""SoAI - Native backend hardware compatibility preconditions [backend/core/hardware/native_compatibility.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.gpu_binding import gpu_binding_selected_device_ids
from core.config.gpu_binding_devices import (
    collect_gpu_binding_available_entries,
    resolve_gpu_binding_selected_entries,
)
from core.errors.exceptions import ValidationError
from core.hardware.gpu_architecture import read_observed_nvidia_architecture_code

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "require_cpu_instruction_features",
    "require_cuda_13_device_support",
)

CPU_FEATURE_OBSERVATION_COMPLETE = "complete"
CUDA_13_UNSUPPORTED_NVIDIA_ARCHITECTURES = frozenset((2, 3, 4, 5))
CUDA_DEVICE_ARCHITECTURE_REASON = "cuda_device_architecture_unsupported"
CPU_FEATURES_REASON = "native_cpu_features_unsupported"


def _cuda_devices(
    gpu_binding: JSONValue, gpu_inventory: Mapping[str, JSONValue]
) -> list[JSONDict] | None:
    selected_ids = gpu_binding_selected_device_ids(gpu_binding)
    if not selected_ids:
        devices = [
            entry
            for entry in collect_gpu_binding_available_entries(gpu_inventory)
            if entry.get("type") == "nvidia"
        ]
        observed_ids = [
            device_id.strip()
            for entry in devices
            if isinstance(device_id := entry.get("device_id"), str)
        ]
        return devices if len(set(observed_ids)) == len(devices) else None
    try:
        return resolve_gpu_binding_selected_entries(gpu_inventory, selected_ids)
    except ValidationError:
        return None


def _unsupported_cuda_13_devices(
    gpu_binding: JSONValue, gpu_inventory: Mapping[str, JSONValue] | None
) -> list[JSONDict]:
    if gpu_inventory is not None and "component_status" in gpu_inventory:
        metadata = gpu_inventory.get("component_status")
        gpu_status = metadata.get("gpu") if isinstance(metadata, dict) else None
        if (
            not isinstance(gpu_status, dict)
            or gpu_status.get("status") != "available"
            or gpu_status.get("sampled_current") is False
        ):
            return []
    devices = None if gpu_inventory is None else _cuda_devices(gpu_binding, gpu_inventory)
    if not devices or not all(
        entry.get("type") == "nvidia"
        and read_observed_nvidia_architecture_code(entry)
        in CUDA_13_UNSUPPORTED_NVIDIA_ARCHITECTURES
        for entry in devices
    ):
        return []
    return devices


def require_cuda_13_device_support(
    gpu_binding: JSONValue, gpu_inventory: Mapping[str, JSONValue] | None
) -> None:
    devices = _unsupported_cuda_13_devices(gpu_binding, gpu_inventory)
    if not devices:
        return
    details: JSONDict = {"reason": CUDA_DEVICE_ARCHITECTURE_REASON}
    device_id = devices[0].get("device_id")
    if len(devices) == 1 and isinstance(device_id, str):
        details["device_id"] = device_id
    raise ValidationError(
        "The installed CUDA 13 backend cannot run on the selected NVIDIA GPU architecture.",
        details=details,
    )


def require_cpu_instruction_features(
    capabilities: Mapping[str, JSONValue], required: Sequence[str]
) -> None:
    if capabilities.get("cpu_features_observation") != CPU_FEATURE_OBSERVATION_COMPLETE:
        return
    observed = capabilities.get("cpu_features")
    if not isinstance(observed, list) or not all(isinstance(feature, str) for feature in observed):
        return
    features = {feature.lower() for feature in observed if isinstance(feature, str)}
    missing: list[JSONValue] = [feature for feature in required if feature not in features]
    if missing:
        raise ValidationError(
            "This processor lacks CPU instructions that the installed backend variant requires.",
            details={"reason": CPU_FEATURES_REASON, "missing_cpu_features": missing},
        )
