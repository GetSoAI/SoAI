"""SoAI - Single model list formatting [backend/models/list_formatting_single_model.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.models.provider_backing import get_model_provider_id, is_provider_backed_model
from core.models.source_identifier import require_source_model_id, write_source_model_id
from core.openai.effective_profile import compute_effective_openai_model_profile
from core.state.plugin_health_resolution import plugin_state_is_available
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_names import (
    ORCH_STATE_LOADING,
    ORCH_STATE_PROCESSING,
    ORCH_STATE_STARTING,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
    PLUGIN_STATE_ABSENT,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.state.state_transition_sets import (
    DISPATCH_READY_STATES,
    LOADED_ORCHESTRATOR_STATES,
)
from core.validation.boolean_coercion import (
    coerce_bool_with_default,
    coerce_payload_bool,
)
from core.validation.strings import coerce_optional_trimmed_str
from models.capabilities.openai_profile_resolution import compose_model_openai_base_profile
from models.list_formatting_status import get_model_status_message
from models.manager.capabilities import derive_model_category_type, derive_model_type

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict

__all__ = (
    "format_single_model_for_list",
    "get_model_display_name",
    "is_model_orphaned",
)

LOGGER_NAME = "SoAI.models.list_formatting_single_model"
EXCLUSIVE_MODEL_RUNTIME_STATES = frozenset(
    {
        ORCH_STATE_STARTING,
        ORCH_STATE_LOADING,
        ORCH_STATE_PROCESSING,
        ORCH_STATE_STOPPING,
    },
)


def get_model_display_name(
    model_data: JSONDict,
    providers_map: dict[str, JSONDict],
    plugin_display_name_map: dict[str, str],
) -> tuple[str, bool]:
    if display_name := coerce_optional_trimmed_str(model_data.get("display_name")):
        return display_name, True
    source_model_id = require_source_model_id(model_data)
    provider_id = get_model_provider_id(model_data)
    if provider_id and (provider_entry := providers_map.get(provider_id)):
        provider_name = coerce_optional_trimmed_str(provider_entry.get("name"))
        raw_upstream_model_id = coerce_optional_trimmed_str(
            model_data.get("raw_upstream_model_id"),
        )
        if provider_name and raw_upstream_model_id:
            return f"{provider_name}/{raw_upstream_model_id}", False
        if provider_name:
            return f"{provider_name}/{source_model_id}", False
    plugin_name = coerce_optional_trimmed_str(model_data.get("plugin")) or "unknown"
    return f"{plugin_display_name_map.get(plugin_name, plugin_name)}/{source_model_id}", False


def is_model_orphaned(model_data: JSONDict) -> bool:
    plugin_name = coerce_optional_trimmed_str(model_data.get("plugin"))
    plugin_catalog_state = coerce_optional_trimmed_str(
        model_data.get("plugin_catalog_state"),
    )
    return (
        not plugin_name or not plugin_catalog_state or plugin_catalog_state == PLUGIN_STATE_ABSENT
    )


def _resolve_model_runtime_status(
    *,
    plugin_status: str,
    universal_id: str | None,
    runtime_model_universal_id: str | None,
    shared_model_runtime: bool,
    provider_backed: bool,
) -> str:
    if shared_model_runtime:
        if plugin_status in DISPATCH_READY_STATES:
            return PLUGIN_STATE_PERSISTENT_READY
        if provider_backed and plugin_status in PROVIDER_BACKED_IGNORED_PLUGIN_STATES:
            return PLUGIN_STATE_PERSISTENT_READY
        return plugin_status
    if (
        plugin_status in EXCLUSIVE_MODEL_RUNTIME_STATES
        and universal_id != runtime_model_universal_id
    ):
        return ORCH_STATE_STOPPED
    return plugin_status


def format_single_model_for_list(
    model_data: JSONDict,
    plugin_states: ImmutablePluginStates,
    provider_map: dict[str, JSONDict],
    backend_status_map: dict[str, JSONDict],
    plugin_info_map: dict[str, JSONDict],
    runtime_model_map: dict[str, str],
    model_has_custom_parameters: bool,
    display_name_map: dict[str, str],
) -> JSONDict:
    universal_id_value = model_data.get("universal_id")
    universal_id = universal_id_value if isinstance(universal_id_value, str) else None
    model_id_value = model_data.get("model_id")
    model_id = model_id_value.strip() if isinstance(model_id_value, str) else ""
    if not model_id:
        raise ValidationError("Model record is missing model_id.")
    plugin_name = coerce_optional_trimmed_str(model_data.get("plugin")) or "unknown"
    is_orphaned = is_model_orphaned(model_data)
    plugin_state = plugin_states.get(plugin_name) or {}
    provider_id = get_model_provider_id(model_data)
    provider_backed = is_provider_backed_model(model_data)
    display_name, has_alias = get_model_display_name(model_data, provider_map, display_name_map)
    plugin_info = plugin_info_map.get(plugin_name)
    model_type = derive_model_type(model_data, plugin_info)
    backend_status_payload = backend_status_map.get(plugin_name)
    no_backend = isinstance(backend_status_payload, Mapping) and not coerce_payload_bool(
        backend_status_payload.get("installed"),
        logger=get_logger(LOGGER_NAME),
        operation="models.list_formatting.coerce_payload_bool",
        default=True,
    )
    provider_info: JSONDict | None = None
    if provider_id and (provider_entry := provider_map.get(provider_id)):
        provider_info = {
            "id": provider_id,
            "name": (
                provider_entry.get("name") if isinstance(provider_entry, dict) else provider_entry
            ),
        }
        if isinstance(provider_entry, dict):
            provider_info.update(
                {
                    key: provider_entry.get(last_key)
                    for key, last_key in [
                        ("api_url", "api_url"),
                        ("status", "last_status"),
                        ("last_error", "last_error"),
                        ("last_checked_at_ms", "last_checked_at_ms"),
                        ("context_window_tokens", "context_window_tokens"),
                        ("created_at_ms", "created_at_ms"),
                    ]
                    if provider_entry.get(last_key) is not None
                },
            )
    plugin_status_value = plugin_state.get("status", PLUGIN_STATE_NOT_DETECTED)
    plugin_status = (
        plugin_status_value if isinstance(plugin_status_value, str) else PLUGIN_STATE_NOT_DETECTED
    )
    persistent_runtime = coerce_bool_with_default(
        plugin_info.get("persistent") if plugin_info is not None else None,
        default=False,
        strict=True,
    )
    shared_model_runtime = persistent_runtime or provider_backed
    runtime_model_universal_id = runtime_model_map.get(plugin_name)
    model_runtime_status = _resolve_model_runtime_status(
        plugin_status=plugin_status,
        universal_id=universal_id,
        runtime_model_universal_id=runtime_model_universal_id,
        shared_model_runtime=shared_model_runtime,
        provider_backed=provider_backed,
    )
    is_enabled = coerce_bool_with_default(model_data.get("is_enabled"), default=True, strict=True)
    response: JSONDict = {
        "id": display_name,
        "name": display_name,
        "plugin": plugin_name,
        "model_id": model_id,
        "universal_id": universal_id,
        "type": derive_model_category_type(model_data, plugin_info),
        "has_alias": has_alias,
        "model_repository": (plugin_info.get("model_repository") if plugin_info else None),
        "description": model_data.get("description", ""),
        "is_loaded": (not shared_model_runtime and plugin_status in LOADED_ORCHESTRATOR_STATES)
        and universal_id == runtime_model_universal_id,
        "plugin_status": model_runtime_status,
        "status": model_data.get("status", "active"),
        "is_enabled": is_enabled,
        "is_available": plugin_state_is_available(plugin_state, provider_backed=provider_backed)
        and (not is_orphaned)
        and is_enabled
        and (model_data.get("status") == "active"),
        "model_has_custom_parameters": model_has_custom_parameters,
        "parameter_version": model_data.get("parameter_version", 0),
        "is_orphaned": is_orphaned,
        "status_message": get_model_status_message(
            model_data,
            plugin_state,
            is_orphaned,
            no_backend,
            provider_backed=provider_backed,
        ),
        "created_at_ms": model_data.get("created_at_ms"),
        "last_modified_at_ms": model_data.get("last_modified_at_ms"),
        "last_discovered_at_ms": model_data.get("last_discovered_at_ms"),
        "last_used_at_ms": model_data.get("last_used_at_ms"),
        "file_modified_at_ms": model_data.get("file_modified_at_ms"),
        "request_count": model_data.get("request_count", 0),
        "size_bytes": model_data.get("size_bytes"),
        "path": model_data.get("path"),
        "family": model_data.get("family"),
        "license": model_data.get("license"),
        "quantization": model_data.get("quantization"),
        "capabilities": model_data.get("capabilities", []),
        "tags": model_data.get("tags", []),
        "provider": provider_info,
    }
    if provider_id:
        response["provider_id"] = provider_id
    if raw_upstream_model_id := coerce_optional_trimmed_str(
        model_data.get("raw_upstream_model_id"),
    ):
        response["raw_upstream_model_id"] = raw_upstream_model_id
    if provider_info is not None:
        response["provider_metadata"] = provider_info
    write_source_model_id(response, model_data)
    overrides_value = model_data.get("openai_capabilities_overrides")
    overrides = overrides_value if isinstance(overrides_value, dict) else None
    if overrides is not None:
        response["openai_capabilities_overrides"] = dict(overrides)
    if plugin_info is not None:
        base_profile = compose_model_openai_base_profile(
            plugin_profile=plugin_info,
            model_data=model_data,
        )
        effective_modalities, effective_caps = compute_effective_openai_model_profile(
            base_modalities=base_profile.get("modalities"),
            base_openai_capabilities=base_profile.get("openai_capabilities"),
            overrides=overrides or {},
        )
        response["modalities"] = effective_modalities
        response["openai_capabilities"] = effective_caps
    if model_type:
        response["model_type"] = model_type
    return response
