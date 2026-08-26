"""SoAI - Plugin GPU binding device validation [backend/core/config/gpu_binding_devices.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
from core.errors.exceptions import ValidationError
from core.types.json import JSONDict, is_json_dict
from core.validation.numbers import coerce_int_from_json

if TYPE_CHECKING:
    from core.config.gpu_binding import GpuBindingRuntimeFamily
    from core.types.json import JSONValue

__all__ = (
    "collect_gpu_binding_available_entries",
    "GpuBindingVisibilityTokens",
    "is_gpu_binding_eligible_entry",
    "resolve_gpu_binding_visibility_tokens",
    "validate_gpu_binding_device_ids",
    "validate_gpu_binding_runtime",
)

_CUDA_UUID_TOKEN_KEYS = ("gpu_uuid", "cuda_uuid", "nvidia_uuid")
_CUDA_INDEX_TOKEN_KEYS = ("cuda_index", "nvidia_index", "vendor_id", "index")
_ROCM_INDEX_TOKEN_KEYS = ("rocm_index", "amd_index", "vendor_id", "index")
_XPU_INDEX_TOKEN_KEYS = ("xpu_index", "intel_index", "vendor_id", "index")


@dataclass(frozen=True, slots=True)
class GpuBindingVisibilityTokens:
    values: tuple[str, ...]
    uses_numeric_indices: bool


def is_gpu_binding_eligible_entry(entry: JSONDict) -> bool:
    if _entry_device_id(entry) is None:
        return False
    compute_capable = entry.get("compute_capable")
    if isinstance(compute_capable, bool) and not compute_capable:
        return False
    if _entry_runtime_inactive(entry):
        return False
    memory_total = coerce_int_from_json(
        entry.get("memory_total_mb"),
        default=None,
        allow_bool=False,
    )
    return memory_total is None or memory_total > 0


def validate_gpu_binding_device_ids(binding: JSONDict, snapshot: JSONDict) -> None:
    selected_ids = gpu_binding_selected_device_ids(binding)
    if not selected_ids:
        return
    _selected_gpu_entries(snapshot, selected_ids)


def validate_gpu_binding_runtime(
    binding: JSONDict,
    snapshot: JSONDict,
    runtime_family: GpuBindingRuntimeFamily,
) -> None:
    selected_ids = gpu_binding_selected_device_ids(binding)
    if not selected_ids:
        return
    if runtime_family == GPU_BINDING_RUNTIME_NONE:
        raise ValidationError(
            "GPU_BINDING selected GPUs, but the installed backend runtime does not support GPU binding.",
        )
    selected_gpus = _selected_gpu_entries(snapshot, selected_ids)
    if runtime_family in {GPU_BINDING_RUNTIME_CUDA, GPU_BINDING_RUNTIME_CUDA_INDEX}:
        resolve_gpu_binding_visibility_tokens(selected_gpus, runtime_family)
        return
    if runtime_family == GPU_BINDING_RUNTIME_ROCM:
        resolve_gpu_binding_visibility_tokens(selected_gpus, runtime_family)
        return
    if runtime_family == GPU_BINDING_RUNTIME_XPU:
        resolve_gpu_binding_visibility_tokens(selected_gpus, runtime_family)
        return
    if runtime_family == GPU_BINDING_RUNTIME_VULKAN_GGML:
        return
    raise ValidationError("GPU_BINDING runtime family is unsupported.")


def collect_gpu_binding_available_entries(
    snapshot: Mapping[str, JSONValue],
) -> list[JSONDict]:
    gpu_payload = snapshot.get("gpu")
    if not is_json_dict(gpu_payload):
        return []
    gpus_value = gpu_payload.get("gpus")
    if not isinstance(gpus_value, list):
        return []
    entries: list[JSONDict] = []
    for entry in gpus_value:
        if is_json_dict(entry) and is_gpu_binding_eligible_entry(entry):
            entries.append(dict(entry))
    return entries


def resolve_gpu_binding_visibility_tokens(
    selected_gpus: list[JSONDict],
    runtime_family: GpuBindingRuntimeFamily,
) -> GpuBindingVisibilityTokens:
    if runtime_family == GPU_BINDING_RUNTIME_CUDA:
        _validate_selected_gpu_vendor(selected_gpus, "nvidia", "CUDA")
        return _resolve_cuda_visibility_tokens(selected_gpus)
    if runtime_family == GPU_BINDING_RUNTIME_CUDA_INDEX:
        _validate_selected_gpu_vendor(selected_gpus, "nvidia", "CUDA")
        return GpuBindingVisibilityTokens(
            _resolve_numeric_visibility_tokens(
                selected_gpus,
                _CUDA_INDEX_TOKEN_KEYS,
                "CUDA device index",
            ),
            True,
        )
    if runtime_family == GPU_BINDING_RUNTIME_ROCM:
        _validate_selected_gpu_vendor(selected_gpus, "amd", "ROCm")
        return GpuBindingVisibilityTokens(
            _resolve_numeric_visibility_tokens(
                selected_gpus,
                _ROCM_INDEX_TOKEN_KEYS,
                "ROCm device index",
            ),
            True,
        )
    if runtime_family == GPU_BINDING_RUNTIME_XPU:
        _validate_selected_gpu_vendor(selected_gpus, "intel", "XPU")
        return GpuBindingVisibilityTokens(
            _resolve_numeric_visibility_tokens(
                selected_gpus,
                _XPU_INDEX_TOKEN_KEYS,
                "Intel XPU root-device index",
            ),
            True,
        )
    raise ValidationError(
        "GPU_BINDING runtime family does not expose environment visibility tokens."
    )


def _selected_gpu_entries(snapshot: JSONDict, selected_ids: list[str]) -> list[JSONDict]:
    entries = _available_gpu_entries(snapshot)
    available_ids: set[str] = set()
    by_device_id: dict[str, JSONDict] = {}
    for entry in entries:
        device_id = _entry_device_id(entry)
        if device_id is None:
            continue
        available_ids.add(device_id)
        by_device_id[device_id] = entry
    if not available_ids:
        raise ValidationError("GPU_BINDING selected GPUs, but no GPUs are currently available.")
    missing_ids = [device_id for device_id in selected_ids if device_id not in available_ids]
    if missing_ids:
        missing = ", ".join(sorted(missing_ids))
        raise ValidationError(
            f"GPU_BINDING references unavailable GPU device IDs: {missing}",
        )
    return [by_device_id[device_id] for device_id in selected_ids]


def _available_gpu_entries(snapshot: JSONDict) -> list[JSONDict]:
    return collect_gpu_binding_available_entries(snapshot)


def _entry_device_id(entry: JSONDict) -> str | None:
    device_id = entry.get("device_id")
    return device_id.strip() if isinstance(device_id, str) and device_id.strip() else None


def _entry_runtime_inactive(entry: JSONDict) -> bool:
    reason = entry.get("telemetry_unavailable_reason")
    if isinstance(reason, str) and reason.strip().lower() == "driver_inactive":
        return True
    kernel_driver = entry.get("kernel_driver")
    return isinstance(kernel_driver, str) and kernel_driver.strip().lower() == "nouveau"


def _validate_selected_gpu_vendor(
    selected_gpus: list[JSONDict],
    expected_vendor: str,
    runtime_label: str,
) -> None:
    for gpu in selected_gpus:
        vendor_value = gpu.get("type")
        vendor = vendor_value.strip().lower() if isinstance(vendor_value, str) else ""
        if vendor == expected_vendor:
            continue
        label = _entry_device_id(gpu) or str(gpu.get("name") or "GPU")
        expected_vendor_label = expected_vendor.upper()
        raise ValidationError(
            f"GPU_BINDING selected '{label}', but {runtime_label} binding only supports {expected_vendor_label} GPUs.",
        )


def _resolve_cuda_visibility_tokens(selected_gpus: list[JSONDict]) -> GpuBindingVisibilityTokens:
    uuid_tokens: list[str] = []
    missing_uuid = False
    for gpu in selected_gpus:
        token = _entry_string_token(gpu, _CUDA_UUID_TOKEN_KEYS)
        if token is None:
            missing_uuid = True
        else:
            uuid_tokens.append(token)
    if not missing_uuid and len(uuid_tokens) == len(selected_gpus):
        return GpuBindingVisibilityTokens(tuple(uuid_tokens), False)
    return GpuBindingVisibilityTokens(
        _resolve_numeric_visibility_tokens(
            selected_gpus,
            _CUDA_INDEX_TOKEN_KEYS,
            "NVIDIA GPU UUID or CUDA device index",
        ),
        True,
    )


def _resolve_numeric_visibility_tokens(
    selected_gpus: list[JSONDict],
    token_keys: tuple[str, ...],
    token_label: str,
) -> tuple[str, ...]:
    tokens: list[str] = []
    for gpu in selected_gpus:
        token = _entry_numeric_token(gpu, token_keys)
        if token is None:
            label = _entry_device_id(gpu) or str(gpu.get("name") or "GPU")
            raise ValidationError(
                f"GPU_BINDING selected '{label}', but SoAI could not resolve its {token_label}.",
            )
        tokens.append(token)
    return tuple(tokens)


def _entry_string_token(entry: JSONDict, token_keys: tuple[str, ...]) -> str | None:
    for key in token_keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _entry_numeric_token(entry: JSONDict, token_keys: tuple[str, ...]) -> str | None:
    for key in token_keys:
        index = coerce_int_from_json(entry.get(key), default=None, allow_bool=False)
        if index is not None and index >= 0:
            return str(index)
    return None
