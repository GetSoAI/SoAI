"""SoAI - Virtual model service for CRUD operations with validation [backend/models/virtual/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.models.protocols_database import DatabaseModelsProtocol
from core.orchestrator.routing_config import (
    ConstituentModelConfig,
    RoutingConfigHolder,
    VirtualModelConfig,
    is_supported_virtual_model_strategy,
)
from core.state.protocols import StateAggregatorProtocol
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_INCOMPATIBLE,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_UPDATE_ERROR,
)
from core.validation.boolean_coercion import coerce_bool_with_default
from models.internal_protocols import (
    ModelMutationEffectsProtocol,
    VirtualModelCoordinatorProtocol,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "VirtualModelService",
    "VirtualModelServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class VirtualModelServiceDependencies:
    database_models: DatabaseModelsProtocol
    virtual_model_coordinator: VirtualModelCoordinatorProtocol
    state_aggregator: StateAggregatorProtocol
    routing_config_holder: RoutingConfigHolder
    installed_plugin_names_ref: Callable[[], set[str]]
    model_resolve_to_universal_id: Callable[[str], Awaitable[str | None]]
    model_get_info_batch: Callable[[list[str]], Awaitable[dict[str, JSONDict]]]
    model_validate_parameters: Callable[[str, JSONDict], Awaitable[None]]
    mutation_effects: ModelMutationEffectsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="VirtualModelServiceDependencies",
            database_models=self.database_models,
            installed_plugin_names_ref=self.installed_plugin_names_ref,
            model_get_info_batch=self.model_get_info_batch,
            model_resolve_to_universal_id=self.model_resolve_to_universal_id,
            model_validate_parameters=self.model_validate_parameters,
            mutation_effects=self.mutation_effects,
            routing_config_holder=self.routing_config_holder,
            state_aggregator=self.state_aggregator,
            virtual_model_coordinator=self.virtual_model_coordinator,
        )


class VirtualModelService:

    def __init__(self, deps: VirtualModelServiceDependencies) -> None:
        self._deps = deps
        self._mutation_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
            TTLAsyncLockRegistryDependencies(
                ttl_seconds=3600.0,
                max_size=2000,
                cleanup_interval_seconds=300.0,
            ),
        )

    def virtual_model_get(self, name: str) -> VirtualModelConfig | None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Virtual model name is required.")
        return self._deps.routing_config_holder.get_virtual_model(normalized_name)

    async def virtual_model_validate_constituents(
        self,
        models: list[ConstituentModelConfig],
    ) -> None:
        await self._validate_constituent_models(models)

    async def virtual_model_add(
        self,
        virtual_model_config: VirtualModelConfig,
    ) -> VirtualModelConfig:
        self._ensure_virtual_model_mutation_allowed(virtual_model_config.name)
        async with self._mutation_locks.lock(virtual_model_config.name.strip()):
            existing_universal_id = await self._deps.model_resolve_to_universal_id(
                virtual_model_config.name,
            )
            existing_virtual = await self._deps.database_models.get_virtual_model(
                virtual_model_config.name,
            )
            if existing_virtual:
                raise ValidationError(
                    f"Virtual model '{virtual_model_config.name}' already exists.",
                )
            if existing_universal_id:
                raise ValidationError(
                    f"A local model with name/alias '{virtual_model_config.name}' already exists.",
                )
            virtual_model = await self._deps.virtual_model_coordinator.virtual_model_add(
                virtual_model_config,
                self._validate_virtual_model_config,
            )
        await self._notify_model_database_changed()
        return virtual_model

    async def virtual_model_update(self, name: str, updates: JSONDict) -> VirtualModelConfig:
        self._ensure_virtual_model_mutation_allowed(name)
        if not await self._deps.database_models.get_virtual_model(name):
            raise ValidationError(f"Virtual model '{name}' not found.")
        virtual_model = await self._deps.virtual_model_coordinator.virtual_model_update(
            name,
            updates,
            self._validate_virtual_model_config,
        )
        await self._notify_model_database_changed()
        return virtual_model

    async def virtual_model_set_enabled(self, name: str, enabled: bool) -> VirtualModelConfig:
        self._ensure_virtual_model_mutation_allowed(name)
        if not await self._deps.database_models.get_virtual_model(name):
            raise ValidationError(f"Virtual model '{name}' not found.")
        virtual_model = await self._deps.virtual_model_coordinator.virtual_model_set_enabled(
            name,
            enabled,
        )
        await self._notify_model_database_changed()
        return virtual_model

    async def virtual_model_delete(self, name: str) -> bool:
        self._ensure_virtual_model_mutation_allowed(name)
        deleted = await self._deps.virtual_model_coordinator.virtual_model_delete(name)
        if deleted:
            await self._notify_model_database_changed()
        return deleted

    async def _notify_model_database_changed(self) -> None:
        await self._deps.mutation_effects.publish_catalog_changed()

    def _ensure_virtual_model_mutation_allowed(self, name: str) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValidationError("Virtual model name is required.")
        if self._deps.routing_config_holder.has_base_virtual_model(normalized_name):
            raise ValidationError(
                f"Virtual model '{normalized_name}' is defined in MODELS.ROUTING.VIRTUAL_MODELS and cannot be mutated through the API.",
            )

    def _validate_virtual_model_shape(self, virtual_model_config: VirtualModelConfig) -> None:
        if not is_supported_virtual_model_strategy(virtual_model_config.strategy):
            raise ValidationError(
                f"Unsupported virtual model strategy '{virtual_model_config.strategy}'.",
            )
        constituent_models = virtual_model_config.models
        if len(constituent_models) < 2:
            raise ValidationError("A virtual model requires at least two constituent models.")
        universal_ids = [model.universal_id for model in constituent_models]
        if len(universal_ids) != len(set(universal_ids)):
            raise ValidationError("Virtual model constituent models must be unique.")

    async def _validate_virtual_model_config(
        self,
        virtual_model_config: VirtualModelConfig,
    ) -> None:
        self._validate_virtual_model_shape(virtual_model_config)
        await self._validate_constituent_models(virtual_model_config.models)

    async def _validate_constituent_models(self, models: list[ConstituentModelConfig]) -> None:
        universal_ids = [model.universal_id for model in models]
        model_info_map = await self._deps.model_get_info_batch(universal_ids)
        plugin_names: set[str] = set()
        for info in model_info_map.values():
            plugin_value = info.get("plugin")
            if isinstance(plugin_value, str) and plugin_value:
                plugin_names.add(plugin_value)
        plugin_status_map = dict(
            zip(
                plugin_names,
                await asyncio.gather(
                    *[
                        self._deps.state_aggregator.get_plugin_status(plugin_name)
                        for plugin_name in plugin_names
                    ],
                    return_exceptions=False,
                ),
                strict=True,
            ),
        )
        tasks: list[Awaitable[None]] = []
        for model in models:
            model_info = model_info_map.get(model.universal_id)
            if not model_info:
                raise ValidationError(f"Constituent model UID '{model.universal_id}' not found.")
            if model_info.get("status") != "active":
                raise ValidationError(
                    f"Constituent model UID '{model.universal_id}' is not active.",
                )
            if not coerce_bool_with_default(
                model_info.get("is_enabled"),
                default=True,
                strict=True,
            ):
                raise ValidationError(f"Constituent model UID '{model.universal_id}' is disabled.")
            plugin_value = model_info.get("plugin")
            if not isinstance(plugin_value, str) or not plugin_value:
                raise ValidationError(
                    f"Constituent model UID '{model.universal_id}' is missing a plugin name.",
                )
            if plugin_value not in self._deps.installed_plugin_names_ref():
                raise ValidationError(
                    f"Constituent model '{model.universal_id}' belongs to a plugin that is not installed.",
                )
            plugin_status = plugin_status_map.get(plugin_value)
            if plugin_status == ORCH_STATE_DISABLED:
                raise ValidationError(
                    f"Constituent model '{model.universal_id}' belongs to a disabled plugin.",
                )
            if plugin_status in [
                PLUGIN_STATE_INSTALL_ERROR,
                PLUGIN_STATE_LOAD_ERROR,
                PLUGIN_STATE_UPDATE_ERROR,
                PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
                PLUGIN_STATE_DELETE_ERROR,
                ORCH_STATE_ERROR,
                PLUGIN_STATE_INCOMPATIBLE,
            ]:
                raise ValidationError(
                    f"Constituent model '{model.universal_id}' belongs to a plugin in error state '{plugin_status}'.",
                )
            if model.parameters:
                tasks.append(
                    self._deps.model_validate_parameters(
                        model.universal_id, dict(model.parameters)
                    ),
                )
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=False)
