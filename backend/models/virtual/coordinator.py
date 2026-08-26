"""SoAI - Virtual model CRUD and cache coordination [backend/models/virtual/coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.ttl_cache import TTLCache
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError, ValidationError
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import (
    ConstituentModelConfig,
    VirtualModelConfig,
)
from core.timing.epoch import epoch_ms
from core.types.json_value import filter_json_mapping_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "VirtualModelCoordinator",
    "VirtualModelCoordinatorDependencies",
    "invalidate_virtual_model_resolution_cache",
)


async def invalidate_virtual_model_resolution_cache(
    resolution_cache_lock: asyncio.Lock,
    resolution_cache: TTLCache[str, str],
    name: str,
) -> None:
    async with resolution_cache_lock:
        resolution_cache.delete(name)


@dataclass(frozen=True, slots=True)
class VirtualModelCoordinatorDependencies:
    database: DatabaseModelsProtocol
    publish: Callable[[], Awaitable[None]]
    resolution_cache_lock: asyncio.Lock
    resolution_cache: TTLCache[str, str]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="VirtualModelCoordinatorDependencies",
            database=self.database,
            publish=self.publish,
            resolution_cache=self.resolution_cache,
            resolution_cache_lock=self.resolution_cache_lock,
        )


class VirtualModelCoordinator:

    def __init__(self, deps: VirtualModelCoordinatorDependencies) -> None:
        self._deps = deps
        self._publish = deps.publish

    async def virtual_model_add(
        self,
        config: VirtualModelConfig,
        validate_callback: Callable[[VirtualModelConfig], Awaitable[None]],
    ) -> VirtualModelConfig:
        await validate_callback(config)
        await self._deps.database.add_or_update_virtual_model(config)
        await self._publish()
        virtual_model = await self._deps.database.get_virtual_model(config.name)
        if not virtual_model:
            raise StateError(f"Virtual model '{config.name}' missing after creation.")
        return virtual_model

    async def virtual_model_update(
        self,
        name: str,
        updates: JSONDict,
        validate_callback: Callable[[VirtualModelConfig], Awaitable[None]],
    ) -> VirtualModelConfig:
        existing = await self._deps.database.get_virtual_model(name)
        if not existing:
            raise ValidationError(f"Virtual model '{name}' not found.")
        updates_models_value = updates.get("models")
        updated_models: list[ConstituentModelConfig] | None = None
        if "models" in updates:
            if not isinstance(updates_models_value, list):
                raise ValidationError("Virtual model updates.models must be a list.")
            updated_models = []
            for model_entry in updates_models_value:
                if not isinstance(model_entry, dict):
                    raise ValidationError("Virtual model updates.models entries must be objects.")
                universal_id_value = model_entry.get("universal_id")
                if not isinstance(universal_id_value, str) or not universal_id_value.strip():
                    raise ValidationError(
                        "Virtual model updates.models entries require a universal_id.",
                    )
                parameters_value = model_entry.get("parameters")
                parameters: JSONDict = {}
                if parameters_value is not None:
                    if not isinstance(parameters_value, dict):
                        raise ValidationError(
                            "Virtual model updates.models parameters must be an object.",
                        )
                    parameters = filter_json_mapping_strict(
                        parameters_value,
                        error_message=(
                            "Virtual model updates.models parameters must be JSON compatible."
                        ),
                    )
                updated_models.append(
                    ConstituentModelConfig(
                        universal_id=universal_id_value,
                        parameters=parameters,
                    ),
                )
        strategy_value = updates.get("strategy")
        strategy = existing.strategy
        if strategy_value is not None:
            if not isinstance(strategy_value, str) or not strategy_value.strip():
                raise ValidationError("Virtual model updates.strategy must be a string.")
            strategy = strategy_value
        updated_virtual_model = VirtualModelConfig(
            name=existing.name,
            strategy=strategy,
            models=updated_models if updated_models is not None else existing.models,
            created_at_ms=existing.created_at_ms,
            last_modified_at_ms=epoch_ms(),
            is_enabled=existing.is_enabled,
        )
        await validate_callback(updated_virtual_model)
        return await self._persist_and_refresh(updated_virtual_model)

    async def virtual_model_set_enabled(self, name: str, enabled: bool) -> VirtualModelConfig:
        existing = await self._deps.database.get_virtual_model(name)
        if not existing:
            raise ValidationError(f"Virtual model '{name}' not found.")
        updated_virtual_model = VirtualModelConfig(
            name=existing.name,
            strategy=existing.strategy,
            models=existing.models,
            created_at_ms=existing.created_at_ms,
            last_modified_at_ms=epoch_ms(),
            is_enabled=enabled,
        )
        return await self._persist_and_refresh(updated_virtual_model)

    async def _persist_and_refresh(self, virtual_model: VirtualModelConfig) -> VirtualModelConfig:
        await self._deps.database.add_or_update_virtual_model(virtual_model)
        await self._publish()
        await invalidate_virtual_model_resolution_cache(
            self._deps.resolution_cache_lock,
            self._deps.resolution_cache,
            virtual_model.name,
        )
        refreshed_virtual_model = await self._deps.database.get_virtual_model(virtual_model.name)
        if not refreshed_virtual_model:
            raise StateError(f"Virtual model '{virtual_model.name}' missing after persistence.")
        return refreshed_virtual_model

    async def virtual_model_delete(self, name: str) -> bool:
        if not await self._deps.database.delete_virtual_model(name):
            return False
        await self._publish()
        await invalidate_virtual_model_resolution_cache(
            self._deps.resolution_cache_lock,
            self._deps.resolution_cache,
            name,
        )
        return True
