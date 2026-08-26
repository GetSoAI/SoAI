"""SoAI - Catalog snapshot for model list building [backend/models/catalog.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import RoutingConfigHolder, VirtualModelConfig
from core.plugins.protocols import PluginManagerProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.protocols import StateAggregatorProtocol
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict

__all__ = (
    "CatalogSnapshot",
    "build_catalog_snapshot",
    "collect_catalog_sources",
)


@dataclass(frozen=True, slots=True)
class CatalogSnapshot:
    plugin_states: ImmutablePluginStates
    state_version: int | None
    database_models: list[JSONDict]
    virtual_models: list[VirtualModelConfig]
    providers_map: dict[str, JSONDict]
    display_name_map: dict[str, str]
    plugin_names: list[str]


async def collect_catalog_sources(
    database_models: DatabaseModelsProtocol,
    database_plugins: DatabasePluginsProtocol,
    plugin_manager: PluginManagerProtocol,
    routing_config_holder: RoutingConfigHolder,
) -> tuple[
    list[JSONDict],
    list[VirtualModelConfig],
    dict[str, JSONDict],
    dict[str, str],
    list[str],
]:
    models_list, providers = await asyncio.gather(
        database_models.list_model_rows(),
        database_plugins.get_all_external_providers(),
        return_exceptions=False,
    )
    virtual_models = routing_config_holder.list_virtual_models()
    providers_map: dict[str, JSONDict] = {}
    for provider_entry in providers:
        provider_entry_json = coerce_json_dict(provider_entry)
        if provider_entry_json is None:
            continue
        provider_id = provider_entry_json.get("id")
        provider_name = provider_entry_json.get("name")
        if not isinstance(provider_id, str) or not isinstance(provider_name, str):
            continue
        providers_map[provider_id] = {
            "name": provider_name,
            "api_url": provider_entry_json.get("api_url"),
            "last_status": provider_entry_json.get("last_status"),
            "last_error": provider_entry_json.get("last_error"),
            "last_checked_at_ms": provider_entry_json.get("last_checked_at_ms"),
            "context_window_tokens": provider_entry_json.get("context_window_tokens"),
            "created_at_ms": provider_entry_json.get("created_at_ms"),
        }
    plugin_names: list[str] = sorted(
        list(
            dict.fromkeys(
                plugin_name
                for model_entry in models_list
                if isinstance((plugin_name := model_entry.get("plugin")), str)
            ),
        ),
    )
    display_name_map = (
        await plugin_manager.get_plugin_display_names(plugin_names) if plugin_names else {}
    )
    return (
        models_list,
        virtual_models,
        providers_map,
        display_name_map,
        plugin_names,
    )


async def build_catalog_snapshot(
    *,
    database_models: DatabaseModelsProtocol,
    database_plugins: DatabasePluginsProtocol,
    plugin_manager: PluginManagerProtocol,
    state_aggregator: StateAggregatorProtocol,
    routing_config_holder: RoutingConfigHolder,
    include_state_version: bool,
) -> CatalogSnapshot:
    (
        models_list,
        virtual_models,
        providers_map,
        display_name_map,
        plugin_names,
    ) = await collect_catalog_sources(
        database_models,
        database_plugins,
        plugin_manager,
        routing_config_holder,
    )
    if include_state_version:
        plugin_states, state_version = await state_aggregator.get_all_plugin_states_with_version()
    else:
        plugin_states = await state_aggregator.get_all_plugin_states()
        state_version = None
    return CatalogSnapshot(
        plugin_states=plugin_states,
        state_version=state_version,
        database_models=models_list,
        virtual_models=virtual_models,
        providers_map=providers_map,
        display_name_map=display_name_map,
        plugin_names=plugin_names,
    )
