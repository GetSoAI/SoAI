"""SoAI - Model list formatting with plugin state enrichment [backend/models/list_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict
from operator import itemgetter
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.models.protocols import ParameterManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.models.provider_backing import is_provider_backed_model
from core.serialization.json_parsing import parse_json_value
from core.state.plugin_health_resolution import plugin_state_is_available
from core.state.state_names import (
    ORCH_STATE_LOADING,
    ORCH_STATE_STARTING,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.state.state_transition_sets import LOADED_ORCHESTRATOR_STATES
from core.types.json import is_json_value
from core.types.json_value import coerce_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from models.capabilities.openai_profile_resolution import build_virtual_openai_profile
from models.catalog import CatalogSnapshot
from models.context_window_resolution import (
    resolve_context_windows_for_catalog_snapshot,
)
from models.list_formatting_single_model import (
    format_single_model_for_list,
    get_model_display_name,
    is_model_orphaned,
)
from models.list_formatting_status import get_model_status_message

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_formatted_model_list",
    "get_model_display_name",
    "get_model_status_message",
)


async def build_formatted_model_list(
    catalog_snapshot: CatalogSnapshot,
    installed_plugin_names: set[str],
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
    get_plugin_info_cached: Callable[[str], Awaitable[JSONDict | None]],
) -> dict[str, list[JSONDict]]:
    models_by_plugin: dict[str, list[JSONDict]] = defaultdict(list)
    loaded_model_map: dict[str, str] = {}
    loaded_state_set = {
        ORCH_STATE_STARTING,
        ORCH_STATE_LOADING,
        PLUGIN_STATE_PERSISTENT_READY,
        *LOADED_ORCHESTRATOR_STATES,
    }
    for model in catalog_snapshot.database_models:
        plugin_name = coerce_optional_trimmed_str(model.get("plugin"))
        if plugin_name:
            models_by_plugin[plugin_name].append(model)
    for plugin_name in models_by_plugin:
        plugin_state_info = catalog_snapshot.plugin_states.get(plugin_name) or {}
        plugin_status = plugin_state_info.get("status")
        details = plugin_state_info.get("details")
        universal_id = (
            coerce_optional_trimmed_str(details.get("universal_id"))
            if isinstance(details, Mapping)
            else None
        )
        if universal_id and plugin_status in loaded_state_set:
            loaded_model_map[plugin_name] = universal_id
    plugin_info_map: dict[str, JSONDict] = {}
    backend_status_map: dict[str, JSONDict] = {}
    if catalog_snapshot.plugin_names:
        plugin_info_map = {
            name: info
            for name, info in zip(
                catalog_snapshot.plugin_names,
                await asyncio.gather(
                    *[get_plugin_info_cached(name) for name in catalog_snapshot.plugin_names],
                    return_exceptions=False,
                ),
                strict=True,
            )
            if info
        }
    for plugin_name, plugin_info in plugin_info_map.items():
        backend_status = _coerce_backend_status(plugin_info.get("backend_status"))
        if backend_status is not None:
            backend_status_map[plugin_name] = backend_status
    hidden_plugins = {
        plugin_name
        for plugin_name in installed_plugin_names
        if not plugin_state_is_available(
            catalog_snapshot.plugin_states.get(plugin_name) or {},
            provider_backed=False,
        )
    }
    provider_visible_plugins = {
        plugin_name
        for model in catalog_snapshot.database_models
        if (plugin_name := coerce_optional_trimmed_str(model.get("plugin")))
        and is_provider_backed_model(model)
        and plugin_state_is_available(
            catalog_snapshot.plugin_states.get(plugin_name) or {},
            provider_backed=True,
        )
    }
    owning_plugin_names = {
        plugin_name
        for model in catalog_snapshot.database_models
        if (plugin_name := coerce_optional_trimmed_str(model.get("plugin")))
        and not is_model_orphaned(model)
    }
    has_custom_map: dict[str, bool] = {}
    universal_ids: list[str] = []
    for model in catalog_snapshot.database_models:
        universal_id_value = model.get("universal_id")
        if isinstance(universal_id_value, str) and universal_id_value:
            universal_ids.append(universal_id_value)
    if universal_ids:
        with_custom = await database_models.get_universal_ids_with_custom_parameters(universal_ids)
        custom_set = set(with_custom)
        has_custom_map = {
            universal_id: (universal_id in custom_set) for universal_id in universal_ids
        }
    context_by_universal_id = await resolve_context_windows_for_catalog_snapshot(
        catalog_snapshot,
        database_models=database_models,
        param_manager=param_manager,
    )
    grouped_models: dict[str, list[JSONDict]] = {
        plugin_name: []
        for plugin_name in installed_plugin_names | owning_plugin_names
        if plugin_name not in hidden_plugins or plugin_name in provider_visible_plugins
    }
    grouped_models.update({"virtual": [], "orphaned": []})
    formatted_models_by_universal_id: dict[str, JSONDict] = {}
    for model_data in catalog_snapshot.database_models:
        universal_id_value = model_data.get("universal_id")
        universal_id = universal_id_value if isinstance(universal_id_value, str) else None
        plugin_name = coerce_optional_trimmed_str(model_data.get("plugin"))
        provider_backed = is_provider_backed_model(model_data)
        orphaned = is_model_orphaned(model_data)
        if not universal_id or (
            plugin_name
            and not orphaned
            and not plugin_state_is_available(
                catalog_snapshot.plugin_states.get(plugin_name) or {},
                provider_backed=provider_backed,
            )
        ):
            continue
        formatted_model = format_single_model_for_list(
            model_data,
            catalog_snapshot.plugin_states,
            catalog_snapshot.providers_map,
            backend_status_map,
            plugin_info_map,
            loaded_model_map,
            has_custom_map.get(universal_id, False),
            catalog_snapshot.display_name_map,
        )
        if context_tokens := context_by_universal_id.get(universal_id):
            formatted_model["context_window_tokens"] = context_tokens
        formatted_models_by_universal_id[universal_id] = formatted_model
        formatted_plugin_value = formatted_model.get("plugin")
        formatted_plugin = (
            formatted_plugin_value if isinstance(formatted_plugin_value, str) else "unknown"
        )
        target_key = "orphaned" if formatted_model["is_orphaned"] else formatted_plugin
        if target_key in grouped_models:
            grouped_models[target_key].append(formatted_model)
    virtual_entries: list[JSONDict] = []
    for virtual_model in catalog_snapshot.virtual_models:
        models_payload: list[JSONValue] = []
        constituent_profiles: list[JSONDict] = []
        for model_entry in virtual_model.models:
            entry_payload = asdict(model_entry)
            if not is_json_value(entry_payload):
                raise StateError("Virtual model entry contains non-JSON values.")
            models_payload.append(entry_payload)
            constituent_profile = formatted_models_by_universal_id.get(model_entry.universal_id)
            if constituent_profile is None:
                continue
            if constituent_profile.get("is_available") is not True:
                continue
            constituent_profiles.append(constituent_profile)
        virtual_entry: JSONDict = {
            "id": virtual_model.name,
            "name": virtual_model.name,
            "type": "virtual",
            "model_type": "virtual",
            "strategy": virtual_model.strategy,
            "models": models_payload,
            "is_enabled": virtual_model.is_enabled,
            "created_at_ms": virtual_model.created_at_ms,
            "last_modified_at_ms": virtual_model.last_modified_at_ms,
        }
        virtual_profile = build_virtual_openai_profile(constituent_profiles)
        if virtual_profile is not None:
            virtual_entry.update(virtual_profile)
        virtual_entries.append(virtual_entry)
    grouped_models["virtual"] = virtual_entries
    return {key: sorted(value, key=itemgetter("id")) for key, value in grouped_models.items()}


def _coerce_backend_status(value: JSONValue) -> JSONDict | None:
    if isinstance(value, str) and value.strip():
        parsed = parse_json_value(value, field="plugin backend_status")
        return coerce_json_dict(parsed)
    return coerce_json_dict(value)
