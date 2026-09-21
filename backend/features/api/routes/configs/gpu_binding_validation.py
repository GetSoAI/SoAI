"""SoAI - Config API GPU binding validation [backend/features/api/routes/configs/gpu_binding_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.config.gpu_binding import (
    GPU_BINDING_CONFIG_KEY,
    normalize_gpu_binding_config,
    normalize_gpu_binding_runtime_family,
)
from core.config.gpu_binding_devices import (
    validate_gpu_binding_device_ids,
    validate_gpu_binding_runtime,
)
from core.errors.exceptions import ValidationError
from core.plugins.backend_variant_status import (
    read_installed_backend_variant_id,
    status_reports_installed_backend,
)
from core.plugins.backend_variants import require_backend_variant_id
from core.plugins.errors import PluginCapabilityError
from core.serialization.json import normalize_for_json
from core.types.json import JSONDict, JSONValue, is_json_dict
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_action_not_supported, raise_invalid_request

if TYPE_CHECKING:
    from core.config.gpu_binding import GpuBindingRuntimeFamily

__all__ = (
    "validate_gpu_binding_backend_variant_selection",
    "validate_gpu_binding_patch",
)


async def validate_gpu_binding_backend_variant_selection(
    request: Request,
    config_name: str,
    backend_variant_id: JSONValue,
    api_context: ApiContext,
) -> None:
    binding = await _load_current_gpu_binding(config_name, api_context)
    if binding is None or binding.get("mode") != "selected":
        return
    try:
        await api_context.dependencies.plugin_manager.ensure_plugin_capability(
            config_name,
            "SUPPORTS_GPU_BINDING",
            "GPU Binding",
        )
    except PluginCapabilityError as exception:
        raise_action_not_supported(request, str(exception))
    runtime_family = await _runtime_family_from_backend_variant_id(
        config_name,
        require_backend_variant_id(backend_variant_id),
        api_context,
    )
    snapshot = await api_context.dependencies.hw_manager.get_system_info(
        components=["gpu"],
        cache=False,
    )
    if runtime_family is None:
        validate_gpu_binding_device_ids(binding, snapshot)
    else:
        validate_gpu_binding_runtime(binding, snapshot, runtime_family)


async def validate_gpu_binding_patch(
    request: Request,
    config_name: str,
    expanded_changes: JSONDict,
    current_config: JSONDict,
    api_context: ApiContext,
) -> None:
    if GPU_BINDING_CONFIG_KEY not in expanded_changes:
        return
    if config_name == "core":
        raise_invalid_request(request, "GPU_BINDING is only valid for plugin configurations.")
    normalized = normalize_gpu_binding_config(expanded_changes.get(GPU_BINDING_CONFIG_KEY))
    current_normalized = _normalize_current_gpu_binding(
        current_config.get(GPU_BINDING_CONFIG_KEY),
    )
    expanded_changes[GPU_BINDING_CONFIG_KEY] = normalized
    if current_normalized == normalized:
        return
    try:
        await api_context.dependencies.plugin_manager.ensure_plugin_capability(
            config_name,
            "SUPPORTS_GPU_BINDING",
            "GPU Binding",
        )
    except PluginCapabilityError as exception:
        raise_action_not_supported(request, str(exception))
    if normalized.get("mode") == "selected":
        snapshot = await api_context.dependencies.hw_manager.get_system_info(
            components=["gpu"],
            cache=False,
        )
        runtime_family = await _resolve_gpu_binding_runtime_family(config_name, api_context)
        if runtime_family is None:
            validate_gpu_binding_device_ids(normalized, snapshot)
        else:
            validate_gpu_binding_runtime(normalized, snapshot, runtime_family)


def _normalize_current_gpu_binding(value: JSONValue) -> JSONDict | None:
    if value is None:
        return None
    try:
        return normalize_gpu_binding_config(value)
    except ValidationError:
        return None


async def _load_current_gpu_binding(
    config_name: str,
    api_context: ApiContext,
) -> JSONDict | None:
    loaded_config = await api_context.dependencies.config_manager.load_config(
        config_name,
        force_reload=True,
    )
    if loaded_config is None:
        return None
    normalized_config = normalize_for_json(loaded_config)
    if not is_json_dict(normalized_config):
        raise_invalid_request(
            api_context.request,
            f"Configuration '{config_name}' is not a mapping.",
        )
    binding_value = normalized_config.get(GPU_BINDING_CONFIG_KEY)
    if binding_value is None:
        return None
    return normalize_gpu_binding_config(binding_value)


async def _resolve_gpu_binding_runtime_family(
    config_name: str,
    api_context: ApiContext,
) -> GpuBindingRuntimeFamily | None:
    runtime_family = await _runtime_family_from_selected_backend_variant(config_name, api_context)
    if runtime_family is not None:
        return runtime_family
    status_payload = await _load_loaded_plugin_status_payload(config_name, api_context)
    runtime_family = _runtime_family_from_status(status_payload)
    if runtime_family is not None:
        return runtime_family
    return None


async def _load_loaded_plugin_status_payload(
    config_name: str,
    api_context: ApiContext,
) -> JSONDict:
    instance = await api_context.dependencies.plugin_manager.get_plugin_instance(config_name)
    if instance is None:
        return {}
    status_payload = await instance.get_status()
    return status_payload if isinstance(status_payload, dict) else {}


def _runtime_family_from_status(status_payload: JSONDict) -> GpuBindingRuntimeFamily | None:
    if not status_reports_installed_backend(status_payload):
        return None
    runtime_family = normalize_gpu_binding_runtime_family(
        status_payload.get("gpu_binding_runtime_family"),
    )
    if runtime_family is not None:
        return runtime_family
    return normalize_gpu_binding_runtime_family(read_installed_backend_variant_id(status_payload))


async def _runtime_family_from_selected_backend_variant(
    config_name: str,
    api_context: ApiContext,
) -> GpuBindingRuntimeFamily | None:
    payload = await api_context.dependencies.plugin_manager.get_backend_variants(
        config_name,
        discover_installed_variant=False,
    )
    selected_value = payload.get("selected_variant_id")
    if not isinstance(selected_value, str) or not selected_value.strip():
        return None
    options_value = payload.get("options")
    if not isinstance(options_value, list):
        return None
    for option_value in options_value:
        if not is_json_dict(option_value):
            continue
        option_id = option_value.get("id")
        if option_id == selected_value:
            return normalize_gpu_binding_runtime_family(
                option_value.get("gpu_binding_runtime_family"),
            )
    return None


async def _runtime_family_from_backend_variant_id(
    config_name: str,
    backend_variant_id: str,
    api_context: ApiContext,
) -> GpuBindingRuntimeFamily | None:
    payload = await api_context.dependencies.plugin_manager.get_backend_variants(
        config_name,
        discover_installed_variant=False,
    )
    options_value = payload.get("options")
    if not isinstance(options_value, list):
        return None
    for option_value in options_value:
        if not is_json_dict(option_value):
            continue
        option_id = option_value.get("id")
        if option_id == backend_variant_id:
            return normalize_gpu_binding_runtime_family(
                option_value.get("gpu_binding_runtime_family"),
            )
    return None
