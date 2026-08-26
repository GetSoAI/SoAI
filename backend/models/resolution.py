"""SoAI - Model name and alias resolution to universal IDs [backend/models/resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from core.concurrency.ttl_cache import TTLCache
from core.di.validation import require_dependencies
from core.models.external_provider_record import normalize_external_provider_name
from core.models.model_info_fields import is_model_info_active_and_enabled
from core.models.protocols_database import DatabaseModelsProtocol
from core.models.universal_id import is_universal_id
from core.plugins.protocols import PluginManagerProtocol

__all__ = (
    "ModelResolutionService",
    "ModelResolutionServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class ModelResolutionServiceDependencies:
    database_models: DatabaseModelsProtocol
    plugin_manager: PluginManagerProtocol
    installed_plugin_names_ref: Callable[[], set[str]]
    resolution_cache: TTLCache[str, str]
    resolution_cache_lock: asyncio.Lock

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelResolutionServiceDependencies",
            database_models=self.database_models,
            installed_plugin_names_ref=self.installed_plugin_names_ref,
            plugin_manager=self.plugin_manager,
            resolution_cache=self.resolution_cache,
            resolution_cache_lock=self.resolution_cache_lock,
        )


class ModelResolutionService:

    def __init__(self, deps: ModelResolutionServiceDependencies) -> None:
        self._deps = deps

    async def model_resolve_to_universal_id(self, name_or_alias: str) -> str | None:
        normalized_name = name_or_alias.strip()
        if not normalized_name:
            return None
        async with self._deps.resolution_cache_lock:
            cached_universal_id = self._deps.resolution_cache.get(normalized_name)
            if isinstance(cached_universal_id, str) and cached_universal_id:
                return cached_universal_id
        resolved_universal_id: str | None = None
        if is_universal_id(normalized_name):
            model_info = await self._deps.database_models.get_model_info(normalized_name)
            if model_info and model_info.get("status") == "active":
                resolved_universal_id = normalized_name
        if not resolved_universal_id and "/" in normalized_name:
            resolved_universal_id = await self._resolve_slashed_name(normalized_name)
        if resolved_universal_id:
            async with self._deps.resolution_cache_lock:
                self._deps.resolution_cache.put(normalized_name, resolved_universal_id)
        return resolved_universal_id

    async def _resolve_slashed_name(self, name_or_alias: str) -> str | None:
        name_prefix, name_suffix = name_or_alias.split("/", 1)
        await self._deps.plugin_manager.require_ready()
        normalized_suffix = name_suffix.strip()
        if not normalized_suffix:
            return None
        normalized_plugin_name = self._deps.plugin_manager.normalize_plugin_name(name_prefix)
        if normalized_plugin_name in self._deps.installed_plugin_names_ref():
            resolved_by_plugin = (
                await self._deps.database_models.resolve_by_plugin_and_source_model_id(
                    normalized_plugin_name,
                    normalized_suffix,
                )
            )
            if resolved_by_plugin:
                return resolved_by_plugin
        provider_canonical_name = normalize_external_provider_name(name_prefix)
        if provider_canonical_name is None:
            return None
        return await self._deps.database_models.resolve_by_provider_and_source_model_id(
            provider_canonical_name,
            normalized_suffix,
        )

    async def model_check_exists(self, universal_id: str) -> bool:
        if not is_universal_id(universal_id):
            return False
        model_info = await self._deps.database_models.get_model_info(universal_id)
        return is_model_info_active_and_enabled(model_info)

    def model_get_installed_plugin_names(self) -> list[str]:
        return sorted(self._deps.installed_plugin_names_ref())

    async def model_invalidate_resolution_cache(self) -> None:
        async with self._deps.resolution_cache_lock:
            self._deps.resolution_cache.clear()
