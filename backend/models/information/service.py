"""SoAI - Model metadata retrieval and API response formatting [backend/models/information/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import is_json_dict
from core.validation.strings import coerce_optional_trimmed_str
from models.context_window_resolution import resolve_context_window_for_model
from models.information.dependencies import ModelInformationServiceDependencies
from models.information.list_cache import ModelInformationListCache
from models.information.openai_list_builder import (
    build_openai_formatted_detail,
)
from models.information.parameter_payload_builder import (
    build_formatted_parameters_payload,
)
from models.manager.capabilities import (
    normalize_modalities_value,
    normalize_openai_capabilities_value,
)
from models.resolved_record import enrich_resolved_model_record

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.types.json import JSONDict, JSONValue

__all__ = ("ModelInformationService",)


class ModelInformationService:

    def __init__(self, deps: ModelInformationServiceDependencies) -> None:
        self._deps = deps
        self._list_cache = ModelInformationListCache(
            deps,
            self.model_get_plugin_capability_profile,
        )

    async def model_get_info(self, universal_id: str) -> JSONDict | None:
        normalized_universal_id = universal_id.strip()
        if not normalized_universal_id:
            raise ValidationError("universal_id is required.")
        model_info = await self._deps.model_registry.model_get_info(normalized_universal_id)
        if model_info is None:
            return None
        plugin_name = coerce_optional_trimmed_str(model_info.get("plugin"))
        plugin_info = (
            await self._deps.model_registry.get_plugin_info(plugin_name) if plugin_name else None
        )
        return enrich_resolved_model_record(model_info, plugin_info)

    async def model_get_info_batch(self, universal_ids: list[str]) -> dict[str, JSONDict]:
        info_map = await self._deps.database_models.get_models_info(universal_ids)
        if not info_map:
            return info_map
        plugin_records: dict[str, JSONDict | None] = {}
        plugin_names: list[str] = []
        for entry in info_map.values():
            if not entry:
                continue
            plugin_name = coerce_optional_trimmed_str(entry.get("plugin"))
            if plugin_name:
                plugin_names.append(plugin_name)
        ordered_plugins = sorted(dict.fromkeys(plugin_names))
        if ordered_plugins:
            plugin_records = dict(
                zip(
                    ordered_plugins,
                    await asyncio.gather(
                        *[
                            self._deps.model_registry.get_plugin_info(plugin_name)
                            for plugin_name in ordered_plugins
                        ],
                        return_exceptions=False,
                    ),
                    strict=True,
                ),
            )
        for entry in info_map.values():
            if entry:
                plugin_name = coerce_optional_trimmed_str(entry.get("plugin")) or ""
                plugin_record = plugin_records.get(plugin_name) if plugin_name else None
                entry.update(enrich_resolved_model_record(entry, plugin_record))
        return info_map

    async def model_get_plugin_capability_profile(self, plugin_name: str) -> JSONDict:
        plugin_info = await self._deps.model_registry.get_plugin_info(plugin_name)
        if not plugin_info:
            raise ValidationError(f"Plugin '{plugin_name}' not found.")
        modalities = normalize_modalities_value(plugin_info.get("modalities"))
        modalities_payload: list[JSONValue] = []
        for modality in modalities:
            modalities_payload.append(modality)
        return {
            "modalities": modalities_payload,
            "openai_capabilities": normalize_openai_capabilities_value(
                plugin_info.get("openai_capabilities"),
            ),
        }

    async def model_invalidate_list_caches(self) -> None:
        await self._list_cache.invalidate()

    async def model_get_openai_formatted_list(self) -> JSONDict:
        return await self._list_cache.get_openai_formatted_list()

    async def model_get_available(self) -> list[JSONDict]:
        result = await self.model_get_openai_formatted_list()
        data = result.get("data")
        if not isinstance(data, list):
            raise ValidationError("OpenAI model list payload is invalid (missing data).")
        models: list[JSONDict] = []
        for item in data:
            if not is_json_dict(item):
                raise ValidationError("OpenAI model list payload is invalid (non-object entry).")
            models.append(item)
        return models

    async def model_get_openai_formatted(
        self,
        model_id: str,
        model_resolve_to_universal_id: Callable[[str], Awaitable[str | None]],
    ) -> JSONDict | None:
        return await build_openai_formatted_detail(
            database_models=self._deps.database_models,
            param_manager=self._deps.param_manager,
            state_aggregator=self._deps.state_aggregator,
            routing_config_holder=self._deps.routing_config_holder,
            installed_plugin_names_ref=self._deps.installed_plugin_names_ref,
            model_get_plugin_capability_profile=self.model_get_plugin_capability_profile,
            model_get_external_provider_for_model=self._deps.model_registry.get_external_provider_for_model,
            model_id=model_id,
            model_resolve_to_universal_id=model_resolve_to_universal_id,
        )

    async def model_get_formatted_parameters(self, universal_id: str) -> JSONDict:
        return await build_formatted_parameters_payload(
            deps=self._deps,
            universal_id=universal_id,
            model_get_info=self.model_get_info,
        )

    async def model_get_formatted_list(self) -> dict[str, list[JSONDict]]:
        return await self._list_cache.get_formatted_list()

    async def model_resolve_context_window(
        self,
        universal_id: str,
        *,
        model_info: JSONDict | None = None,
        provider_record: ExternalProviderInternalRecord | JSONDict | None = None,
        provider_record_resolved: bool = False,
    ) -> int | None:
        resolved_model_info = model_info
        if resolved_model_info is None:
            resolved_model_info = await self.model_get_info(universal_id)
        if resolved_model_info is None:
            return None
        if provider_record is None and not provider_record_resolved:
            provider_record = await self._deps.model_registry.get_external_provider_for_model(
                universal_id,
            )
        return await resolve_context_window_for_model(
            model_data=resolved_model_info,
            database_models=self._deps.database_models,
            param_manager=self._deps.param_manager,
            provider_record=provider_record,
        )
