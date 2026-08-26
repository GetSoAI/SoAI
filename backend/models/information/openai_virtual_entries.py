"""SoAI - Virtual OpenAI model entry builders [backend/models/information/openai_virtual_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.validation.strings import coerce_optional_trimmed_str
from models.capabilities.openai_profile_resolution import (
    build_virtual_openai_profile,
    resolve_effective_openai_profile,
)
from models.information.openai_availability import is_model_available_for_openai_api
from models.information.openai_entries import (
    build_virtual_model_openai_entry,
    enrich_entry_with_capability_profile,
)
from models.information.openai_entry_profiles import resolve_catalog_openai_model_id

if TYPE_CHECKING:
    from core.models.protocols_database import DatabaseModelsProtocol
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_virtual_openai_detail_entry",
    "build_virtual_openai_list_entry",
)


def build_virtual_openai_list_entry(
    *,
    virtual_model: VirtualModelConfig,
    model_profiles_by_universal_id: dict[str, JSONDict],
) -> JSONDict | None:
    entry = build_virtual_model_openai_entry(virtual_model.name, virtual_model.created_at_ms)
    constituent_profiles: list[JSONDict] = []
    for model_entry in virtual_model.models:
        profile = model_profiles_by_universal_id.get(model_entry.universal_id)
        if profile is not None:
            constituent_profiles.append(profile)
    if not constituent_profiles:
        return None
    virtual_profile = build_virtual_openai_profile(constituent_profiles)
    if virtual_profile is not None:
        enrich_entry_with_capability_profile(entry, virtual_profile)
    return entry


async def build_virtual_openai_detail_entry(
    *,
    database_models: DatabaseModelsProtocol,
    state_aggregator: StateAggregatorProtocol,
    installed_plugin_names_ref: Callable[[], set[str]],
    model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
    virtual_model: VirtualModelConfig,
) -> JSONDict | None:
    entry = build_virtual_model_openai_entry(virtual_model.name, virtual_model.created_at_ms)
    universal_ids = [
        model_entry.universal_id
        for model_entry in virtual_model.models
        if isinstance(model_entry.universal_id, str) and model_entry.universal_id
    ]
    if not universal_ids:
        return None
    model_rows = await database_models.get_models_info(universal_ids)
    plugin_states = await state_aggregator.get_all_plugin_states()
    plugin_profiles: dict[str, JSONDict] = {}
    constituent_profiles: list[JSONDict] = []
    for model_entry in virtual_model.models:
        model_row = model_rows.get(model_entry.universal_id)
        if not isinstance(model_row, dict):
            continue
        if not is_model_available_for_openai_api(
            model_row,
            all_plugin_states=plugin_states,
            installed_plugin_names_ref=installed_plugin_names_ref,
        ):
            continue
        plugin_name = coerce_optional_trimmed_str(model_row.get("plugin"))
        if not plugin_name:
            continue
        if plugin_name not in plugin_profiles:
            plugin_profiles[plugin_name] = await model_get_plugin_capability_profile(plugin_name)
        overrides_value = model_row.get("openai_capabilities_overrides")
        overrides = overrides_value if isinstance(overrides_value, dict) else None
        constituent_profiles.append(
            resolve_effective_openai_profile(
                model_id=resolve_catalog_openai_model_id(model_row),
                base_profile=plugin_profiles[plugin_name],
                overrides=overrides,
            ),
        )
    if not constituent_profiles:
        return None
    virtual_profile = build_virtual_openai_profile(constituent_profiles)
    if virtual_profile is not None:
        enrich_entry_with_capability_profile(entry, virtual_profile)
    return entry
