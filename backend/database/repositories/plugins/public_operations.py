"""SoAI - Plugin repository public operations [backend/database/repositories/plugins/public_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.protocols import DatabaseCoreProtocol
from core.database.provider_mutation_requests import (
    ProviderCreateMutationRequest,
    ProviderDeleteMutationRequest,
    ProviderMutationOutcome,
    ProviderUpdateMutationRequest,
)
from core.plugins.protocols_database import (
    CircuitBreakerStatePayload,
    PluginRuntimeProcessesPayload,
)
from core.runtime.backend_process_tracking import BackendProcessIdentity
from core.types.json import JSONDict, JSONValue
from database.repositories.plugins.backend_variants import (
    sync_update_backend_variant_available_count,
)
from database.repositories.plugins.catalog_metadata import (
    sync_update_plugin_catalog_metadata,
)
from database.repositories.plugins.internal_protocols import (
    DatabasePluginsBackendVariantCountSurface,
    DatabasePluginsProviderMethodsSurface,
    DatabasePluginsRuntimeProcessesSurface,
)
from database.repositories.plugins.provider_methods import (
    get_all_circuit_breaker_states_method,
    get_all_external_providers_method,
    get_external_provider_method,
    list_providers_for_plugin_method,
    mutate_create_provider_method,
    mutate_delete_provider_method,
    mutate_update_provider_method,
    update_provider_status_method,
    upsert_circuit_breaker_state_method,
    upsert_plugin_managed_provider_method,
)
from database.repositories.plugins.runtime_processes_methods import (
    clear_runtime_processes_method,
    get_runtime_processes_method,
    list_plugins_with_runtime_processes_method,
    set_runtime_processes_method,
)
from database.repositories.plugins.settings import (
    get_system_setting_query,
    sync_set_system_setting,
)
from database.repositories.plugins.state import sync_update_plugin_runtime_loaded

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord

__all__ = ("DatabasePluginsOperations",)


class DatabasePluginsOperations:
    if not TYPE_CHECKING:
        core: DatabaseCoreProtocol

    async def update_plugin_catalog_metadata(
        self: DatabasePluginsBackendVariantCountSurface,
        plugin_name: str,
        *,
        parameter_schema: JSONDict | None = None,
        backend_variant_options: list[JSONDict] | None = None,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_update_plugin_catalog_metadata,
            plugin_name,
            parameter_schema,
            backend_variant_options,
        )

    async def update_backend_variant_available_count(
        self: DatabasePluginsBackendVariantCountSurface,
        plugin_name: str,
        expected_state: str,
        available_count: int,
    ) -> bool:
        result = await self.core.writer.queue_write_operation(
            sync_update_backend_variant_available_count,
            plugin_name,
            expected_state,
            available_count,
        )
        return result

    async def update_plugin_runtime_loaded(
        self: DatabasePluginsBackendVariantCountSurface,
        plugin_name: str,
        runtime_loaded: bool,
    ) -> None:
        await self.core.writer.queue_write_operation(
            sync_update_plugin_runtime_loaded,
            plugin_name,
            runtime_loaded,
        )

    async def list_providers_for_plugin(
        self: DatabasePluginsProviderMethodsSurface,
        plugin_name: str,
    ) -> list[ExternalProviderInternalRecord]:
        return await list_providers_for_plugin_method(self, plugin_name)

    async def get_external_provider(
        self: DatabasePluginsProviderMethodsSurface,
        provider_id: str,
        *,
        decrypt_key: bool = False,
    ) -> ExternalProviderInternalRecord | None:
        return await get_external_provider_method(
            self,
            provider_id,
            decrypt_key=decrypt_key,
        )

    async def get_all_external_providers(
        self: DatabasePluginsProviderMethodsSurface,
    ) -> list[JSONDict]:
        return await get_all_external_providers_method(self)

    async def upsert_plugin_managed_provider(
        self: DatabasePluginsProviderMethodsSurface,
        plugin_name: str,
        provider_id: str,
        name: str,
        url: str,
    ) -> ExternalProviderInternalRecord | None:
        return await upsert_plugin_managed_provider_method(
            self,
            plugin_name,
            provider_id,
            name,
            url,
        )

    async def mutate_update_provider(
        self: DatabasePluginsProviderMethodsSurface,
        request: ProviderUpdateMutationRequest,
    ) -> ProviderMutationOutcome:
        return await mutate_update_provider_method(self, request)

    async def mutate_create_provider(
        self: DatabasePluginsProviderMethodsSurface,
        request: ProviderCreateMutationRequest,
    ) -> ProviderMutationOutcome:
        return await mutate_create_provider_method(self, request)

    async def mutate_delete_provider(
        self: DatabasePluginsProviderMethodsSurface,
        request: ProviderDeleteMutationRequest,
    ) -> ProviderMutationOutcome:
        return await mutate_delete_provider_method(self, request)

    async def update_provider_status(
        self: DatabasePluginsProviderMethodsSurface,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        await update_provider_status_method(self, provider_id, status, error)

    async def get_all_circuit_breaker_states(
        self: DatabasePluginsProviderMethodsSurface,
    ) -> list[JSONDict]:
        return await get_all_circuit_breaker_states_method(self)

    async def upsert_circuit_breaker_state(
        self: DatabasePluginsProviderMethodsSurface,
        plugin_name: str,
        state: CircuitBreakerStatePayload,
    ) -> None:
        await upsert_circuit_breaker_state_method(self, plugin_name, state)

    async def get_system_setting(
        self: DatabasePluginsBackendVariantCountSurface,
        key: str,
    ) -> JSONValue | None:
        return await self.core.reader.execute_read(get_system_setting_query, key)

    async def set_system_setting(
        self: DatabasePluginsBackendVariantCountSurface,
        key: str,
        value: JSONValue,
    ) -> None:
        await self.core.writer.queue_write_operation(sync_set_system_setting, key, value)

    async def get_runtime_processes(
        self: DatabasePluginsRuntimeProcessesSurface,
        plugin_name: str,
    ) -> list[BackendProcessIdentity]:
        return await get_runtime_processes_method(self, plugin_name)

    async def set_runtime_processes(
        self: DatabasePluginsRuntimeProcessesSurface,
        plugin_name: str,
        identities: list[BackendProcessIdentity],
    ) -> None:
        await set_runtime_processes_method(
            self,
            plugin_name,
            identities,
        )

    async def clear_runtime_processes(
        self: DatabasePluginsRuntimeProcessesSurface,
        plugin_name: str,
    ) -> None:
        await clear_runtime_processes_method(
            self,
            plugin_name,
        )

    async def list_plugins_with_runtime_processes(
        self: DatabasePluginsRuntimeProcessesSurface,
    ) -> list[PluginRuntimeProcessesPayload]:
        return await list_plugins_with_runtime_processes_method(self)
