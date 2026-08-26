"""SoAI - Database plugin provider and circuit-breaker methods [backend/database/repositories/plugins/provider_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.provider_mutation_requests import (
    ProviderCreateMutationRequest,
    ProviderDeleteMutationRequest,
    ProviderMutationOutcome,
    ProviderMutationReplayRequest,
    ProviderUpdateMutationRequest,
)
from core.plugins.protocols_database import CircuitBreakerStatePayload
from database.repositories.plugins.internal_protocols import (
    DatabasePluginsProviderMethodsSurface,
)
from database.repositories.plugins.provider_delete_mutation import sync_delete_provider_v1
from database.repositories.plugins.provider_mutation_persistence import (
    read_provider_mutation_outcome,
)
from database.repositories.plugins.provider_mutations import (
    sync_create_provider_v1,
    sync_update_provider_v1,
)
from database.repositories.plugins.provider_read_queries import (
    get_all_external_providers_query,
    get_external_provider_async_query,
    list_providers_for_plugin_query,
)
from database.repositories.plugins.providers import (
    sync_update_provider_status,
    sync_upsert_plugin_managed_provider,
)
from database.repositories.plugins.settings import (
    get_all_circuit_breaker_states_query,
    sync_upsert_circuit_breaker_state,
)
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.types.json import JSONDict

__all__ = (
    "get_all_circuit_breaker_states_method",
    "get_all_external_providers_method",
    "get_external_provider_method",
    "list_providers_for_plugin_method",
    "mutate_delete_provider_method",
    "mutate_create_provider_method",
    "mutate_update_provider_method",
    "read_provider_mutation_outcome_method",
    "update_provider_status_method",
    "upsert_circuit_breaker_state_method",
    "upsert_plugin_managed_provider_method",
)


async def list_providers_for_plugin_method(
    self: DatabasePluginsProviderMethodsSurface,
    plugin_name: str,
) -> list[ExternalProviderInternalRecord]:
    return await self.core.reader.execute_read(
        list_providers_for_plugin_query,
        self.fernet,
        plugin_name,
    )


async def get_external_provider_method(
    self: DatabasePluginsProviderMethodsSurface,
    provider_id: str,
    *,
    decrypt_key: bool = False,
) -> ExternalProviderInternalRecord | None:
    return await self.core.reader.execute_read(
        get_external_provider_async_query,
        self.fernet,
        provider_id,
        decrypt_key,
    )


async def get_all_external_providers_method(
    self: DatabasePluginsProviderMethodsSurface,
) -> list[JSONDict]:
    return await self.core.reader.execute_read(get_all_external_providers_query)


async def upsert_plugin_managed_provider_method(
    self: DatabasePluginsProviderMethodsSurface,
    plugin_name: str,
    provider_id: str,
    name: str,
    url: str,
) -> ExternalProviderInternalRecord | None:
    return await self.core.writer.queue_write_operation(
        sync_upsert_plugin_managed_provider,
        self.fernet,
        plugin_name,
        provider_id,
        name,
        url,
    )


async def mutate_update_provider_method(
    self: DatabasePluginsProviderMethodsSurface,
    request: ProviderUpdateMutationRequest,
) -> ProviderMutationOutcome:
    outcome = await self.core.writer.queue_write_operation(
        sync_update_provider_v1,
        request,
        self.fernet,
    )
    notify_domain_event_outbox_dispatch_requested(self.event_bus)
    return outcome


async def mutate_create_provider_method(
    self: DatabasePluginsProviderMethodsSurface,
    request: ProviderCreateMutationRequest,
) -> ProviderMutationOutcome:
    outcome = await self.core.writer.queue_write_operation(
        sync_create_provider_v1,
        request,
        self.fernet,
    )
    notify_domain_event_outbox_dispatch_requested(self.event_bus)
    return outcome


async def mutate_delete_provider_method(
    self: DatabasePluginsProviderMethodsSurface,
    request: ProviderDeleteMutationRequest,
) -> ProviderMutationOutcome:
    outcome = await self.core.writer.queue_write_operation(
        sync_delete_provider_v1,
        request,
    )
    notify_domain_event_outbox_dispatch_requested(self.event_bus)
    return outcome


async def read_provider_mutation_outcome_method(
    self: DatabasePluginsProviderMethodsSurface,
    request: ProviderMutationReplayRequest,
) -> ProviderMutationOutcome | None:
    return await self.core.reader.execute_read(read_provider_mutation_outcome, request)


async def update_provider_status_method(
    self: DatabasePluginsProviderMethodsSurface,
    provider_id: str,
    status: str,
    error: str | None = None,
) -> None:
    updated = await self.core.writer.queue_write_operation(
        sync_update_provider_status,
        provider_id,
        status,
        error,
    )
    if updated:
        notify_domain_event_outbox_dispatch_requested(self.event_bus)


async def get_all_circuit_breaker_states_method(
    self: DatabasePluginsProviderMethodsSurface,
) -> list[JSONDict]:
    return await self.core.reader.execute_read(get_all_circuit_breaker_states_query)


async def upsert_circuit_breaker_state_method(
    self: DatabasePluginsProviderMethodsSurface,
    plugin_name: str,
    state: CircuitBreakerStatePayload,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_upsert_circuit_breaker_state,
        plugin_name,
        state,
    )
