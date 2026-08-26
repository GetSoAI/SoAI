"""SoAI - OpenAI model list construction from catalog snapshot [backend/models/information/openai_list_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.model_capability_catalog import (
    build_model_capability_catalog_entry,
    build_model_capability_catalog_payload,
)
from core.validation.strings import coerce_optional_trimmed_str
from models.catalog import build_catalog_snapshot
from models.context_window_resolution import (
    resolve_context_window_for_model,
    resolve_context_windows_for_catalog_snapshot,
)
from models.information.openai_availability import is_model_available_for_openai_api
from models.information.openai_entries import model_sort_key
from models.information.openai_entry_profiles import (
    build_profiled_openai_model_entry,
    require_openai_plugin_name,
    resolve_catalog_openai_model_id,
)
from models.information.openai_virtual_entries import (
    build_virtual_openai_detail_entry,
    build_virtual_openai_list_entry,
)

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.models.protocols import ParameterManagerProtocol
    from core.models.protocols_database import DatabaseModelsProtocol
    from core.orchestrator.routing_config import RoutingConfigHolder
    from core.plugins.protocols import PluginManagerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_openai_formatted_detail",
    "build_openai_formatted_list",
)


async def build_openai_formatted_list(
    *,
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
    database_plugins: DatabasePluginsProtocol,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    routing_config_holder: RoutingConfigHolder,
    installed_plugin_names_ref: Callable[[], set[str]],
    model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
) -> JSONDict:
    catalog_snapshot = await build_catalog_snapshot(
        database_models=database_models,
        database_plugins=database_plugins,
        plugin_manager=plugin_manager,
        state_aggregator=state_aggregator,
        routing_config_holder=routing_config_holder,
        include_state_version=False,
    )
    seen_ids: set[str] = set()
    model_entries: list[JSONDict] = []
    plugin_profiles: dict[str, JSONDict] = {}
    model_profiles_by_universal_id: dict[str, JSONDict] = {}
    context_by_universal_id = await resolve_context_windows_for_catalog_snapshot(
        catalog_snapshot,
        database_models=database_models,
        param_manager=param_manager,
    )
    for model_data in catalog_snapshot.database_models:
        if not is_model_available_for_openai_api(
            model_data,
            all_plugin_states=catalog_snapshot.plugin_states,
            installed_plugin_names_ref=installed_plugin_names_ref,
        ):
            continue
        model_id = resolve_catalog_openai_model_id(model_data)
        if not model_id or model_id in seen_ids:
            continue
        model_universal_id = coerce_optional_trimmed_str(model_data.get("universal_id"))
        entry, effective_profile = await build_profiled_openai_model_entry(
            model_data=model_data,
            model_id=model_id,
            providers_map=catalog_snapshot.providers_map,
            plugin_profiles=plugin_profiles,
            model_get_plugin_capability_profile=model_get_plugin_capability_profile,
            context_window_tokens=(
                context_by_universal_id.get(model_universal_id) if model_universal_id else None
            ),
        )
        if model_universal_id:
            model_profiles_by_universal_id[model_universal_id] = effective_profile
        _append_openai_model_entry_if_new(
            entry=entry,
            model_entries=model_entries,
            seen_ids=seen_ids,
        )
    for virtual_model in catalog_snapshot.virtual_models:
        if not virtual_model.is_enabled:
            continue
        virtual_entry = build_virtual_openai_list_entry(
            virtual_model=virtual_model,
            model_profiles_by_universal_id=model_profiles_by_universal_id,
        )
        if virtual_entry is None:
            continue
        _append_openai_model_entry_if_new(
            entry=virtual_entry,
            model_entries=model_entries,
            seen_ids=seen_ids,
            require_nonempty_id=False,
        )
    return _build_openai_list_response(model_entries)


async def build_openai_formatted_detail(
    *,
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    routing_config_holder: RoutingConfigHolder,
    installed_plugin_names_ref: Callable[[], set[str]],
    model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
    model_get_external_provider_for_model: Callable[
        [str],
        Awaitable[ExternalProviderInternalRecord | None],
    ],
    model_id: str,
    model_resolve_to_universal_id: Callable[[str], Awaitable[str | None]],
) -> JSONDict | None:
    if virtual_model := routing_config_holder.get_virtual_model(model_id):
        if not virtual_model.is_enabled:
            return None
        virtual_entry = await build_virtual_openai_detail_entry(
            database_models=database_models,
            state_aggregator=state_aggregator,
            installed_plugin_names_ref=installed_plugin_names_ref,
            model_get_plugin_capability_profile=model_get_plugin_capability_profile,
            virtual_model=virtual_model,
        )
        if virtual_entry is None:
            return None
        return build_model_capability_catalog_entry(
            virtual_entry,
            context="OpenAI virtual model capability catalog entry",
        )
    local_entry = await _build_openai_formatted_local_detail(
        database_models=database_models,
        param_manager=param_manager,
        state_aggregator=state_aggregator,
        installed_plugin_names_ref=installed_plugin_names_ref,
        model_get_plugin_capability_profile=model_get_plugin_capability_profile,
        model_get_external_provider_for_model=model_get_external_provider_for_model,
        model_id=model_id,
        model_resolve_to_universal_id=model_resolve_to_universal_id,
    )
    if local_entry is None:
        return None
    return build_model_capability_catalog_entry(
        local_entry,
        context="OpenAI local model capability catalog entry",
    )


def _append_openai_model_entry_if_new(
    *,
    entry: JSONDict,
    model_entries: list[JSONDict],
    seen_ids: set[str],
    require_nonempty_id: bool = True,
) -> None:
    model_id_value = entry.get("id")
    model_id = model_id_value if isinstance(model_id_value, str) else ""
    if (require_nonempty_id and not model_id) or model_id in seen_ids:
        return
    model_entries.append(entry)
    seen_ids.add(model_id)


def _build_openai_list_response(model_entries: list[JSONDict]) -> JSONDict:
    sorted_entries = sorted(model_entries, key=model_sort_key)
    return build_model_capability_catalog_payload(sorted_entries)


async def _build_openai_formatted_local_detail(
    *,
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    installed_plugin_names_ref: Callable[[], set[str]],
    model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
    model_get_external_provider_for_model: Callable[
        [str],
        Awaitable[ExternalProviderInternalRecord | None],
    ],
    model_id: str,
    model_resolve_to_universal_id: Callable[[str], Awaitable[str | None]],
) -> JSONDict | None:
    universal_id = await model_resolve_to_universal_id(model_id)
    if not universal_id:
        return None
    model_info = await database_models.get_model_info(universal_id)
    if not model_info:
        return None
    if not is_model_available_for_openai_api(
        model_info,
        all_plugin_states=await state_aggregator.get_all_plugin_states(),
        installed_plugin_names_ref=installed_plugin_names_ref,
    ):
        return None
    require_openai_plugin_name(model_info)
    provider_record = await model_get_external_provider_for_model(universal_id)
    context_window_tokens = await resolve_context_window_for_model(
        model_data=model_info,
        provider_record=provider_record,
        database_models=database_models,
        param_manager=param_manager,
    )
    canonical_model_id = resolve_catalog_openai_model_id(model_info)
    providers_map: dict[str, JSONDict] = {}
    provider_id = coerce_optional_trimmed_str(model_info.get("provider_id"))
    provider_name = (
        coerce_optional_trimmed_str(provider_record.get("name"))
        if provider_record is not None
        else None
    )
    if provider_id and provider_name:
        providers_map[provider_id] = {"name": provider_name}
    entry, _effective_profile = await build_profiled_openai_model_entry(
        model_data=model_info,
        model_id=canonical_model_id,
        providers_map=providers_map,
        plugin_profiles={},
        model_get_plugin_capability_profile=model_get_plugin_capability_profile,
        context_window_tokens=context_window_tokens,
    )
    return entry
