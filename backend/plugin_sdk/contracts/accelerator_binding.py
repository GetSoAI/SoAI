"""SoAI - Plugin SDK accelerator binding resolution [backend/plugin_sdk/contracts/accelerator_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.config.gpu_binding import (
    GPU_BINDING_RUNTIME_CUDA,
    GPU_BINDING_RUNTIME_CUDA_INDEX,
    GPU_BINDING_RUNTIME_NONE,
    GPU_BINDING_RUNTIME_ROCM,
    GPU_BINDING_RUNTIME_VULKAN_GGML,
    GPU_BINDING_RUNTIME_XPU,
    gpu_binding_selected_device_ids,
)
from core.config.gpu_binding_devices import (
    GpuBindingVisibilityTokens,
    collect_gpu_binding_available_entries,
    resolve_gpu_binding_visibility_tokens,
)
from core.errors.exceptions import ConfigurationError, ValidationError
from plugin_sdk.contracts.accelerator_vulkan import resolve_vulkan_visible_devices

if TYPE_CHECKING:
    from core.config.gpu_binding import GpuBindingRuntimeFamily
    from core.types.json import JSONDict, JSONValue

__all__ = ("build_accelerator_binding_environment",)


def build_accelerator_binding_environment(
    plugin_config: Mapping[str, JSONValue],
    *,
    gpu_inventory: Mapping[str, JSONValue] | None,
    runtime_family: str,
) -> dict[str, str]:
    selected_ids = gpu_binding_selected_device_ids(plugin_config.get("GPU_BINDING"))
    if not selected_ids:
        return {}
    if runtime_family == GPU_BINDING_RUNTIME_NONE:
        raise ConfigurationError(
            "GPU_BINDING selected GPUs, but the current backend runtime does not expose "
            "a supported GPU visibility contract.",
        )
    selected_gpus = _selected_gpu_entries(gpu_inventory, selected_ids)
    if runtime_family == GPU_BINDING_RUNTIME_CUDA:
        tokens = _resolve_visibility_tokens(selected_gpus, GPU_BINDING_RUNTIME_CUDA)
        environment = {
            "CUDA_VISIBLE_DEVICES": ",".join(tokens.values),
            "NVIDIA_VISIBLE_DEVICES": ",".join(tokens.values),
        }
        if tokens.uses_numeric_indices:
            environment["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        return environment
    if runtime_family == GPU_BINDING_RUNTIME_CUDA_INDEX:
        tokens = _resolve_visibility_tokens(selected_gpus, GPU_BINDING_RUNTIME_CUDA_INDEX)
        environment = {
            "CUDA_VISIBLE_DEVICES": ",".join(tokens.values),
            "NVIDIA_VISIBLE_DEVICES": ",".join(tokens.values),
        }
        if tokens.uses_numeric_indices:
            environment["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        return environment
    if runtime_family == GPU_BINDING_RUNTIME_ROCM:
        tokens = _resolve_visibility_tokens(selected_gpus, GPU_BINDING_RUNTIME_ROCM)
        mask = ",".join(tokens.values)
        return {
            "HIP_VISIBLE_DEVICES": mask,
            "ROCR_VISIBLE_DEVICES": mask,
            "HSA_VISIBLE_DEVICES": mask,
        }
    if runtime_family == GPU_BINDING_RUNTIME_VULKAN_GGML:
        return {"GGML_VK_VISIBLE_DEVICES": ",".join(resolve_vulkan_visible_devices(selected_gpus))}
    if runtime_family == GPU_BINDING_RUNTIME_XPU:
        tokens = _resolve_visibility_tokens(selected_gpus, GPU_BINDING_RUNTIME_XPU)
        return {"ZE_AFFINITY_MASK": ",".join(tokens.values)}
    raise ConfigurationError(f"Unsupported accelerator runtime family '{runtime_family}'.")


def _selected_gpu_entries(
    gpu_inventory: Mapping[str, JSONValue] | None,
    selected_ids: list[str],
) -> list[JSONDict]:
    if gpu_inventory is None:
        raise ConfigurationError(
            "GPU_BINDING selected GPUs, but no hardware snapshot was provided.",
        )
    entries = collect_gpu_binding_available_entries(gpu_inventory)
    by_device_id: dict[str, JSONDict] = {}
    for entry in entries:
        device_id = _entry_device_id(entry)
        if device_id is not None:
            by_device_id[device_id] = entry
    selected_entries: list[JSONDict] = []
    missing_ids: list[str] = []
    for device_id in selected_ids:
        selected_entry = by_device_id.get(device_id)
        if selected_entry is None:
            missing_ids.append(device_id)
        else:
            selected_entries.append(selected_entry)
    if missing_ids:
        missing = ", ".join(sorted(missing_ids))
        raise ConfigurationError(
            f"GPU_BINDING references unavailable GPU device IDs: {missing}",
        )
    if not selected_entries:
        raise ConfigurationError("GPU_BINDING did not resolve to any available GPUs.")
    return selected_entries


def _entry_device_id(entry: JSONDict) -> str | None:
    device_id = entry.get("device_id")
    return device_id.strip() if isinstance(device_id, str) and device_id.strip() else None


def _resolve_visibility_tokens(
    selected_gpus: list[JSONDict],
    runtime_family: GpuBindingRuntimeFamily,
) -> GpuBindingVisibilityTokens:
    try:
        return resolve_gpu_binding_visibility_tokens(selected_gpus, runtime_family)
    except ValidationError as exception:
        raise ConfigurationError(str(exception)) from exception
