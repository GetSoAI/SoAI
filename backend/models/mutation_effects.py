"""SoAI - Model mutation side effect coordination [backend/models/mutation_effects.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.concurrency.ttl_cache import TTLCache
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.events.protocols import EventBusProtocol
from core.events.types_models_model_events import (
    ModelParametersChangedEvent,
    ModelParametersRequireReloadEvent,
)
from core.models.protocols_database import DatabaseModelsProtocol
from core.types.json import JSONDict
from models.identification import invalidate_resolution_cache_for_model
from models.internal_protocols import AsyncParameterCacheProtocol
from models.mutation_notifications import notify_model_catalog_changed

__all__ = (
    "ModelMutationEffects",
    "ModelMutationEffectsDependencies",
)


@dataclass(frozen=True, slots=True)
class ModelMutationEffectsDependencies:
    database_models: DatabaseModelsProtocol
    parameter_cache: AsyncParameterCacheProtocol
    resolution_cache_lock: asyncio.Lock
    resolution_cache: TTLCache[str, str]
    model_invalidate_list_caches: Callable[[], Awaitable[None]]
    event_bus: EventBusProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelMutationEffectsDependencies",
            database_models=self.database_models,
            event_bus=self.event_bus,
            model_invalidate_list_caches=self.model_invalidate_list_caches,
            parameter_cache=self.parameter_cache,
            resolution_cache=self.resolution_cache,
            resolution_cache_lock=self.resolution_cache_lock,
        )


class ModelMutationEffects:
    def __init__(self, deps: ModelMutationEffectsDependencies) -> None:
        self._deps = deps

    async def publish_catalog_changed(
        self,
        *,
        added_universal_ids: list[str] | None = None,
        removed_universal_ids: list[str] | None = None,
    ) -> None:
        await notify_model_catalog_changed(
            model_invalidate_list_caches=self._deps.model_invalidate_list_caches,
            event_bus=self._deps.event_bus,
            added_universal_ids=added_universal_ids,
            removed_universal_ids=removed_universal_ids,
        )

    async def invalidate_all_resolution_cache(self) -> None:
        async with self._deps.resolution_cache_lock:
            self._deps.resolution_cache.clear()

    async def invalidate_resolution_cache_for_model(self, universal_id: str) -> None:
        await invalidate_resolution_cache_for_model(
            self._deps.resolution_cache_lock,
            self._deps.resolution_cache,
            universal_id,
        )

    async def invalidate_parameter_cache_for_models(self, universal_ids: list[str]) -> None:
        for universal_id in universal_ids:
            await self._deps.parameter_cache.invalidate(universal_id)

    async def finalize_model_deletion(self, universal_id: str) -> None:
        if not await self._deps.database_models.delete_models_by_id(universal_id):
            raise StateError(
                f"Failed to delete model '{universal_id}' from database.",
                operation="models.mutation_effects.finalize_model_deletion",
                details={"universal_id": universal_id},
            )
        await self._deps.parameter_cache.invalidate(universal_id)
        await self.invalidate_resolution_cache_for_model(universal_id)
        await self.publish_catalog_changed(removed_universal_ids=[universal_id])

    async def commit_parameter_changes(
        self,
        *,
        universal_id: str,
        plugin_name: str,
        new_custom: JSONDict,
        reload_needed: bool,
        reload_reason: str,
    ) -> None:
        if not await self._deps.database_models.update_model_parameters(universal_id, new_custom):
            raise StateError(
                f"Failed to save parameters for '{universal_id}' to database.",
                operation="models.mutation_effects.commit_parameter_changes",
                details={"universal_id": universal_id, "plugin_name": plugin_name},
            )
        if reload_needed:
            if await self._deps.database_models.increment_parameter_version(universal_id) < 0:
                raise StateError(
                    f"Failed to increment parameter version for '{universal_id}'.",
                    operation="models.mutation_effects.commit_parameter_changes",
                    details={"universal_id": universal_id, "plugin_name": plugin_name},
                )
        await self._deps.parameter_cache.invalidate(universal_id)
        await self._deps.model_invalidate_list_caches()
        await self._deps.event_bus.publish(ModelParametersChangedEvent(universal_id=universal_id))
        if reload_needed:
            await self._deps.event_bus.publish(
                ModelParametersRequireReloadEvent(
                    plugin_name=plugin_name,
                    universal_id=universal_id,
                    reason=reload_reason,
                ),
            )
