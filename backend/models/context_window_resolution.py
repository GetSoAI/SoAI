"""SoAI - Context window token resolution for models [backend/models/context_window_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.models.context_window import (
    PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW,
    coerce_positive_context_tokens,
    definition_has_default,
    resolve_semantic_parameter_name,
)
from core.validation.strings import coerce_optional_trimmed_str

if TYPE_CHECKING:
    from core.models.external_provider_record import (
        ExternalProviderInternalRecord,
        ExternalProviderRecord,
    )
    from core.models.protocols import ParameterManagerProtocol
    from core.models.protocols_database import DatabaseModelsProtocol
    from core.types.json import JSONDict
    from models.catalog import CatalogSnapshot

    type PluginContextBinding = tuple[str | None, int | None]

__all__ = (
    "resolve_context_window_for_model",
    "resolve_context_windows_for_catalog_snapshot",
    "resolve_context_windows_for_models",
)


async def resolve_context_window_for_model(
    *,
    model_data: JSONDict,
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
    provider_record: (
        ExternalProviderRecord | ExternalProviderInternalRecord | JSONDict | None
    ) = None,
    plugin_context_cache: dict[str, PluginContextBinding] | None = None,
) -> int | None:
    plugin_name = coerce_optional_trimmed_str(model_data.get("plugin"))
    model_context_tokens = coerce_positive_context_tokens(model_data.get("context_window_tokens"))
    if not plugin_name:
        if model_context_tokens is not None:
            return model_context_tokens
        if provider_record is None:
            return None
        return coerce_positive_context_tokens(provider_record.get("context_window_tokens"))
    context_parameter_name: str | None = None
    context_default: int | None = None
    context_parameter_name, context_default = await _resolve_plugin_context_binding(
        plugin_name=plugin_name,
        param_manager=param_manager,
        plugin_context_cache=plugin_context_cache,
    )
    if context_parameter_name:
        universal_id = coerce_optional_trimmed_str(model_data.get("universal_id"))
        if universal_id:
            custom_parameters = await database_models.get_model_custom_parameters(universal_id)
            custom_value = custom_parameters.get(context_parameter_name)
            if custom_tokens := coerce_positive_context_tokens(custom_value):
                return custom_tokens
    if model_context_tokens is not None:
        return model_context_tokens
    if provider_record is not None:
        provider_context_tokens = coerce_positive_context_tokens(
            provider_record.get("context_window_tokens"),
        )
        if provider_context_tokens is not None:
            return provider_context_tokens
    return context_default


async def resolve_context_windows_for_models(
    *,
    model_rows: list[JSONDict],
    provider_map: Mapping[str, JSONDict],
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
) -> dict[str, int]:
    resolved: dict[str, int] = {}
    plugin_context_cache: dict[str, PluginContextBinding] = {}
    for model_data in model_rows:
        universal_id = coerce_optional_trimmed_str(model_data.get("universal_id"))
        if not universal_id:
            continue
        provider_record: JSONDict | None = None
        provider_id = coerce_optional_trimmed_str(model_data.get("provider_id"))
        if provider_id:
            provider_record = provider_map.get(provider_id)
        context_tokens = await resolve_context_window_for_model(
            model_data=model_data,
            provider_record=provider_record,
            database_models=database_models,
            param_manager=param_manager,
            plugin_context_cache=plugin_context_cache,
        )
        if context_tokens is not None:
            resolved[universal_id] = context_tokens
    return resolved


async def resolve_context_windows_for_catalog_snapshot(
    catalog_snapshot: CatalogSnapshot,
    *,
    database_models: DatabaseModelsProtocol,
    param_manager: ParameterManagerProtocol,
) -> dict[str, int]:
    return await resolve_context_windows_for_models(
        model_rows=catalog_snapshot.database_models,
        provider_map=catalog_snapshot.providers_map,
        database_models=database_models,
        param_manager=param_manager,
    )


async def _resolve_plugin_context_binding(
    *,
    plugin_name: str,
    param_manager: ParameterManagerProtocol,
    plugin_context_cache: dict[str, PluginContextBinding] | None,
) -> PluginContextBinding:
    if plugin_context_cache is not None and plugin_name in plugin_context_cache:
        return plugin_context_cache[plugin_name]
    raw_schema = await param_manager.get_all_parameters_for_plugin(plugin_name)
    schema: dict[str, JSONDict] = {
        name: definition
        for name, definition in raw_schema.items()
        if isinstance(name, str) and isinstance(definition, dict)
    }
    context_parameter_name = resolve_semantic_parameter_name(
        schema,
        PARAMETER_SEMANTIC_ROLE_CONTEXT_WINDOW,
    )
    context_default: int | None = None
    if context_parameter_name:
        definition = schema.get(context_parameter_name)
        if definition is not None and definition_has_default(definition):
            context_default = coerce_positive_context_tokens(definition.get("default"))
    binding: PluginContextBinding = (context_parameter_name, context_default)
    if plugin_context_cache is not None:
        plugin_context_cache[plugin_name] = binding
    return binding
