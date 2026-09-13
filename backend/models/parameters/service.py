"""SoAI - Model parameter validation retrieval update and deletion [backend/models/parameters/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.config.reload_policy import reload_sensitive_keys
from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.models.context_parameter_mapping import (
    map_standardized_context_keys,
    map_standardized_context_updates,
    resolve_context_parameter_name,
)
from core.models.protocols import ParameterManagerProtocol
from core.models.protocols_database import DatabaseModelsProtocol
from core.models.universal_id import is_universal_id
from core.types.json import JSONDict
from core.types.json_value import copy_json_dict
from models.internal_protocols import (
    AsyncParameterCacheProtocol,
    ModelMutationEffectsProtocol,
    ModelParameterMutationServiceProtocol,
)
from models.parameters.mutation_ordering import MutationCallable
from models.parameters.schema_access import (
    get_default_parameters,
    get_validated_parameter_schema,
)
from models.parameters.schema_projection import normalize_parameter_schema
from models.parameters.schema_validation import (
    validate_parameter_keys_exist,
    validate_parameter_values,
)

__all__ = (
    "ModelParameterService",
    "ModelParameterServiceDependencies",
)

LOGGER_NAME = "SoAI.models.parameters.service"


@dataclass(frozen=True, slots=True)
class ModelParameterServiceDependencies:
    database_models: DatabaseModelsProtocol
    param_manager: ParameterManagerProtocol
    parameter_mutation_service: ModelParameterMutationServiceProtocol
    parameter_cache: AsyncParameterCacheProtocol
    model_record_locks: AsyncLockRegistryProtocol[str]
    mutation_effects: ModelMutationEffectsProtocol
    metrics: MetricsManagerProtocol
    model_get_info: Callable[[str], Awaitable[JSONDict | None]]
    model_validate_and_get_context: Callable[[str], Awaitable[tuple[JSONDict, str]]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelParameterServiceDependencies",
            database_models=self.database_models,
            metrics=self.metrics,
            model_get_info=self.model_get_info,
            model_record_locks=self.model_record_locks,
            model_validate_and_get_context=self.model_validate_and_get_context,
            mutation_effects=self.mutation_effects,
            param_manager=self.param_manager,
            parameter_cache=self.parameter_cache,
            parameter_mutation_service=self.parameter_mutation_service,
        )


class ModelParameterService:
    def __init__(self, deps: ModelParameterServiceDependencies) -> None:
        self._deps = deps

    async def _get_validated_parameter_schema(self, universal_id: str) -> tuple[str, JSONDict]:
        return await get_validated_parameter_schema(
            universal_id=universal_id,
            model_validate_and_get_context=self._deps.model_validate_and_get_context,
            param_manager=self._deps.param_manager,
        )

    async def model_get_parameters_and_version(self, universal_id: str) -> tuple[JSONDict, int]:
        if not is_universal_id(universal_id):
            return ({}, 0)
        async with self._deps.model_record_locks[universal_id]:
            database_version, cached = await asyncio.gather(
                self._deps.database_models.get_parameter_version(universal_id),
                self._deps.parameter_cache.get(universal_id),
                return_exceptions=False,
            )
            model_info = await self._deps.model_get_info(universal_id)
            if not model_info:
                return ({}, 0)
            parameters = await get_default_parameters(
                self._deps.param_manager,
                str(model_info["plugin"]),
            )
            if cached and cached[1] >= database_version:
                custom_parameters, parameter_version = cached
            else:
                custom_parameters = await self._deps.database_models.get_model_custom_parameters(
                    universal_id,
                )
                parameter_version = database_version
                await self._deps.parameter_cache.put(
                    universal_id,
                    custom_parameters,
                    parameter_version,
                )
            parameters.update(custom_parameters)
            return (copy_json_dict(parameters), parameter_version)

    async def model_get_parameter_definitions(self, universal_id: str) -> JSONDict:
        _plugin_name, schema = await self._get_validated_parameter_schema(universal_id)
        return copy_json_dict(schema)

    async def model_validate_parameters(self, universal_id: str, parameters: JSONDict) -> None:
        plugin_name, schema = await self._get_validated_parameter_schema(universal_id)
        validate_parameter_values(plugin_name=plugin_name, schema=schema, parameters=parameters)

    async def model_validate_parameter_keys_exist(self, universal_id: str, keys: list[str]) -> None:
        plugin_name, schema = await self._get_validated_parameter_schema(universal_id)
        validate_parameter_keys_exist(plugin_name=plugin_name, schema=schema, keys=keys)

    async def model_execute_update_parameters(
        self,
        universal_id: str,
        parameters: JSONDict,
        order: int | None = None,
    ) -> None:
        plugin_name, _schema = await self._get_validated_parameter_schema(universal_id)

        def _mutation(schema: JSONDict, old: JSONDict) -> tuple[JSONDict, bool, str] | None:
            logger = get_logger(LOGGER_NAME)
            validate_parameter_values(
                plugin_name=plugin_name,
                schema=schema,
                parameters=parameters,
            )
            mapped_parameters = map_standardized_context_updates(
                parameters,
                resolve_context_parameter_name(schema),
                schema,
            )
            sanitized = {key: value for key, value in mapped_parameters.items() if key in schema}
            ignored_keys = set(mapped_parameters) - set(sanitized)
            if ignored_keys:
                logger.warning(
                    "Update for [%s] ignored unknown: %s",
                    universal_id,
                    list(ignored_keys),
                )
            updated = {**old, **sanitized}
            schema_definitions = normalize_parameter_schema(schema)
            reload_needed = bool(
                reload_sensitive_keys(
                    schema_definitions,
                    {key for key in set(updated) | set(old) if updated.get(key) != old.get(key)},
                ),
            )
            return (
                updated,
                reload_needed,
                f"Reload-requiring parameters changed for model {universal_id}",
            )

        await self._deps.parameter_mutation_service.mutate(
            universal_id,
            metric_key="param_updates_processed",
            mutation=_mutation,
            order=order,
        )

    async def model_execute_delete_parameters(
        self,
        universal_id: str,
        keys: list[str],
        order: int | None = None,
    ) -> None:
        plugin_name, _schema = await self._get_validated_parameter_schema(universal_id)

        def _mutation(schema: JSONDict, old: JSONDict) -> tuple[JSONDict, bool, str] | None:
            validate_parameter_keys_exist(
                plugin_name=plugin_name,
                schema=schema,
                keys=keys,
            )
            normalized_keys = map_standardized_context_keys(
                keys,
                resolve_context_parameter_name(schema),
                schema,
            )
            if not old:
                return None
            schema_definitions = normalize_parameter_schema(schema)
            return (
                {key: value for key, value in old.items() if key not in normalized_keys},
                bool(
                    reload_sensitive_keys(
                        schema_definitions,
                        [key for key in normalized_keys if key in old],
                    ),
                ),
                f"Custom reload-requiring parameters deleted for model {universal_id}",
            )

        await self._deps.parameter_mutation_service.mutate(
            universal_id,
            metric_key="param_deletes_processed",
            metric_value=len(keys),
            mutation=_mutation,
            order=order,
        )

    async def model_process_parameter_mutation(
        self,
        universal_id: str,
        metric_key: str,
        metric_value: int | None,
        mutation: MutationCallable,
    ) -> None:
        async with self._deps.model_record_locks[universal_id]:
            self._deps.metrics.increment_counter(
                "model_manager",
                metric_key,
                value=metric_value if metric_value is not None else 1,
            )
            (plugin_name, schema), existing_parameters = await asyncio.gather(
                self._get_validated_parameter_schema(universal_id),
                self._deps.database_models.get_model_custom_parameters(universal_id),
                return_exceptions=False,
            )
            if not (response := mutation(schema, existing_parameters)):
                return
            updated_parameters, reload_needed, reload_reason = response
            changed_keys = {
                key
                for key in set(existing_parameters) | set(updated_parameters)
                if existing_parameters.get(key) != updated_parameters.get(key)
            }
            schema_definitions = normalize_parameter_schema(schema)
            if reload_keys := reload_sensitive_keys(schema_definitions, changed_keys):
                reload_needed, reload_reason = (
                    True,
                    (
                        f"{reload_reason} (enforced by manager for keys: {', '.join(sorted(reload_keys))})"
                        if reload_reason
                        else f"Reload-requiring parameters changed: {', '.join(sorted(reload_keys))}"
                    ),
                )
            await self._deps.mutation_effects.commit_parameter_changes(
                universal_id=universal_id,
                plugin_name=plugin_name,
                new_custom=updated_parameters,
                reload_needed=reload_needed,
                reload_reason=reload_reason,
            )
