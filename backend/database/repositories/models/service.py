"""SoAI - Model catalog and custom parameter database service [backend/database/repositories/models/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.orchestrator.routing_config import VirtualModelConfig
from database.repositories.models.catalog_mutations import (
    sync_delete_models_by_universal_ids,
    sync_purge_models_for_plugin,
    sync_record_model_usage,
    sync_set_model_status_for_plugin,
    sync_update_model_alias,
    sync_update_model_enabled,
    sync_update_model_openai_capabilities_overrides,
    sync_upsert_models,
)
from database.repositories.models.catalog_queries import (
    get_all_models_by_plugin_query,
    get_latest_model_usage_query,
    get_model_info_query,
    get_models_info_query,
    list_model_rows_query,
)
from database.repositories.models.parameters import (
    get_model_custom_parameters_query,
    get_parameter_version_query,
    get_universal_ids_with_custom_parameters_query,
    sync_increment_parameter_version,
    sync_update_model_parameters,
)
from database.repositories.models.resolution import (
    resolve_by_plugin_and_source_model_id_query,
    resolve_by_provider_and_source_model_id_query,
)
from database.repositories.models.virtual import (
    find_virtual_models_using_universal_ids_query,
    get_virtual_model_query,
    list_all_virtual_models_query,
    sync_add_or_update_virtual_model,
    sync_delete_virtual_model,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseModels",)


class DatabaseModels:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self._core = deps.core
        self._config = deps.config
        self._fernet = deps.fernet

    async def get_all_models_by_plugin(
        self,
    ) -> dict[str, dict[str, JSONDict]]:
        return await self._core.reader.execute_read(get_all_models_by_plugin_query)

    async def upsert_models(self, models: list[JSONDict]) -> None:
        await self._core.writer.queue_write_operation(
            sync_upsert_models,
            models,
        )

    async def delete_models_by_id(self, universal_id: str) -> bool:
        count = await self._core.writer.queue_write_operation(
            sync_delete_models_by_universal_ids,
            [universal_id],
        )
        return count > 0

    async def delete_models_by_ids(self, universal_ids: list[str]) -> int:
        return await self._core.writer.queue_write_operation(
            sync_delete_models_by_universal_ids,
            universal_ids,
        )

    async def get_model_info(self, universal_id: str) -> JSONDict | None:
        return await self._core.reader.execute_read(get_model_info_query, universal_id)

    async def get_models_info(self, universal_ids: list[str]) -> dict[str, JSONDict]:
        return await self._core.reader.execute_read(get_models_info_query, universal_ids)

    async def list_model_rows(self) -> list[JSONDict]:
        return await self._core.reader.execute_read(list_model_rows_query)

    async def resolve_by_plugin_and_source_model_id(
        self,
        plugin_name: str,
        source_model_id: str,
    ) -> str | None:
        return await self._core.reader.execute_read(
            resolve_by_plugin_and_source_model_id_query,
            plugin_name,
            source_model_id,
        )

    async def resolve_by_provider_and_source_model_id(
        self,
        provider_canonical_name: str,
        source_model_id: str,
    ) -> str | None:
        return await self._core.reader.execute_read(
            resolve_by_provider_and_source_model_id_query,
            provider_canonical_name,
            source_model_id,
        )

    async def set_model_status_for_plugin(
        self,
        plugin_name: str,
        status: str,
    ) -> tuple[int, list[str]]:
        return await self._core.writer.queue_write_operation(
            sync_set_model_status_for_plugin,
            plugin_name,
            status,
        )

    async def get_parameter_version(self, universal_id: str) -> int:
        return await self._core.reader.execute_read(get_parameter_version_query, universal_id)

    async def get_model_custom_parameters(self, universal_id: str) -> JSONDict:
        return await self._core.reader.execute_read(get_model_custom_parameters_query, universal_id)

    async def get_universal_ids_with_custom_parameters(self, universal_ids: list[str]) -> list[str]:
        return await self._core.reader.execute_read(
            get_universal_ids_with_custom_parameters_query,
            universal_ids,
        )

    async def update_model_parameters(self, universal_id: str, parameters: JSONDict) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_update_model_parameters,
            universal_id,
            parameters,
        )

    async def increment_parameter_version(self, universal_id: str) -> int:
        return await self._core.writer.queue_write_operation(
            sync_increment_parameter_version,
            universal_id,
        )

    async def update_model_alias(self, universal_id: str, updates: JSONDict) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_update_model_alias,
            universal_id,
            updates,
        )

    async def update_model_enabled(self, universal_id: str, enabled: bool) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_update_model_enabled,
            universal_id,
            enabled,
        )

    async def record_model_usage(
        self,
        universal_id: str,
        plugin_name: str,
    ) -> tuple[int, int] | None:
        return await self._core.writer.queue_write_operation(
            sync_record_model_usage,
            universal_id,
            plugin_name,
        )

    async def get_latest_model_usage(self) -> JSONDict | None:
        return await self._core.reader.execute_read(get_latest_model_usage_query)

    async def update_model_openai_capabilities_overrides(
        self,
        universal_id: str,
        overrides: JSONDict | None,
    ) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_update_model_openai_capabilities_overrides,
            universal_id,
            overrides,
        )

    async def find_virtual_models_using_universal_ids(
        self,
        universal_ids: list[str],
    ) -> dict[str, list[str]]:
        if not universal_ids:
            return {}
        return await self._core.reader.execute_read(
            find_virtual_models_using_universal_ids_query,
            universal_ids,
        )

    async def add_or_update_virtual_model(self, virtual_model: VirtualModelConfig) -> None:
        await self._core.writer.queue_write_operation(
            sync_add_or_update_virtual_model,
            virtual_model,
        )

    async def delete_virtual_model(self, name: str) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_delete_virtual_model,
            name,
        )

    async def get_virtual_model(self, name: str) -> VirtualModelConfig | None:
        return await self._core.reader.execute_read(get_virtual_model_query, name)

    async def list_all_virtual_models(self) -> list[VirtualModelConfig]:
        return await self._core.reader.execute_read(list_all_virtual_models_query)

    async def purge_models_for_plugin(self, plugin_name: str) -> bool:
        return await self._core.writer.queue_write_operation(
            sync_purge_models_for_plugin,
            plugin_name,
        )
