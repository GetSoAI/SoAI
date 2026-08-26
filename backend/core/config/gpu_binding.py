"""SoAI - Canonical plugin GPU binding configuration [backend/core/config/gpu_binding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, JSONValue, is_json_dict

__all__ = (
    "GPU_BINDING_CONFIG_KEY",
    "GPU_BINDING_MODE_ALL",
    "GPU_BINDING_MODE_SELECTED",
    "GPU_BINDING_RUNTIME_CUDA",
    "GPU_BINDING_RUNTIME_CUDA_INDEX",
    "GPU_BINDING_RUNTIME_NONE",
    "GPU_BINDING_RUNTIME_ROCM",
    "GPU_BINDING_RUNTIME_VULKAN_GGML",
    "GPU_BINDING_RUNTIME_XPU",
    "default_gpu_binding_config",
    "gpu_binding_selected_device_ids",
    "normalize_gpu_binding_config",
    "normalize_gpu_binding_runtime_family",
)

if TYPE_CHECKING:
    from typing import Literal

    type GpuBindingRuntimeFamily = Literal[
        "none", "cuda", "cuda_index", "rocm", "vulkan_ggml", "xpu"
    ]


GPU_BINDING_CONFIG_KEY = "GPU_BINDING"
GPU_BINDING_MODE_ALL = "all"
GPU_BINDING_MODE_SELECTED = "selected"
GPU_BINDING_RUNTIME_NONE: GpuBindingRuntimeFamily = "none"
GPU_BINDING_RUNTIME_CUDA: GpuBindingRuntimeFamily = "cuda"
GPU_BINDING_RUNTIME_CUDA_INDEX: GpuBindingRuntimeFamily = "cuda_index"
GPU_BINDING_RUNTIME_ROCM: GpuBindingRuntimeFamily = "rocm"
GPU_BINDING_RUNTIME_VULKAN_GGML: GpuBindingRuntimeFamily = "vulkan_ggml"
GPU_BINDING_RUNTIME_XPU: GpuBindingRuntimeFamily = "xpu"


def default_gpu_binding_config() -> JSONDict:
    return {"mode": GPU_BINDING_MODE_ALL, "device_ids": []}


def normalize_gpu_binding_config(
    value: JSONValue,
    *,
    require_selected_devices: bool = False,
) -> JSONDict:
    if value is None:
        return default_gpu_binding_config()
    if not is_json_dict(value):
        raise ValidationError("GPU_BINDING must be a JSON object.")
    mode_value = value.get("mode")
    mode = mode_value.strip().lower() if isinstance(mode_value, str) else ""
    if mode not in {GPU_BINDING_MODE_ALL, GPU_BINDING_MODE_SELECTED}:
        raise ValidationError("GPU_BINDING.mode must be 'all' or 'selected'.")
    device_ids = _normalize_device_ids(value.get("device_ids"))
    if mode == GPU_BINDING_MODE_ALL:
        return default_gpu_binding_config()
    if require_selected_devices and not device_ids:
        raise ValidationError("GPU_BINDING.device_ids must include at least one GPU.")
    if not device_ids:
        return default_gpu_binding_config()
    return {"mode": GPU_BINDING_MODE_SELECTED, "device_ids": device_ids}


def gpu_binding_selected_device_ids(value: JSONValue) -> list[str]:
    normalized = normalize_gpu_binding_config(value)
    if normalized.get("mode") != GPU_BINDING_MODE_SELECTED:
        return []
    device_ids = normalized.get("device_ids")
    if not isinstance(device_ids, list):
        return []
    return [device_id for device_id in device_ids if isinstance(device_id, str)]


def normalize_gpu_binding_runtime_family(
    value: JSONValue,
) -> GpuBindingRuntimeFamily | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized == GPU_BINDING_RUNTIME_CUDA:
        return GPU_BINDING_RUNTIME_CUDA
    if normalized == GPU_BINDING_RUNTIME_CUDA_INDEX:
        return GPU_BINDING_RUNTIME_CUDA_INDEX
    if normalized == GPU_BINDING_RUNTIME_ROCM:
        return GPU_BINDING_RUNTIME_ROCM
    if normalized in {"intel", "level_zero", "oneapi", "sycl", GPU_BINDING_RUNTIME_XPU}:
        return GPU_BINDING_RUNTIME_XPU
    if normalized in {"vulkan", GPU_BINDING_RUNTIME_VULKAN_GGML}:
        return GPU_BINDING_RUNTIME_VULKAN_GGML
    if normalized in {"cpu", "none", "metal", "opencl", "openvino"}:
        return GPU_BINDING_RUNTIME_NONE
    return None


def _normalize_device_ids(value: JSONValue) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("GPU_BINDING.device_ids must be a JSON array.")
    device_ids: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError("GPU_BINDING.device_ids must contain non-empty strings.")
        normalized = item.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        device_ids.append(normalized)
    return device_ids
