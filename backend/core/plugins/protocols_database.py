"""SoAI - Plugin database protocol contracts [backend/core/plugins/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypedDict

from core.database.provider_mutation_requests import (
    ProviderCreateMutationRequest,
    ProviderDeleteMutationRequest,
    ProviderMutationOutcome,
    ProviderMutationReplayRequest,
    ProviderUpdateMutationRequest,
)
from core.state.circuit_breaker import CircuitBreakerState
from core.state.compatibility import CompatibilityInfo

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.plugins.protocols_clone_database import DatabasePluginCloneTransactionsProtocol
    from core.runtime.backend_process_tracking import BackendProcessIdentity
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "CircuitBreakerStatePayload",
    "DatabasePluginsProtocol",
    "PluginRuntimeProcessesPayload",
)


class CircuitBreakerStatePayload(TypedDict):
    state: CircuitBreakerState
    failure_count: int
    last_failure_at_ms: int


class PluginRuntimeProcessesPayload(TypedDict):
    plugin_name: str
    state: str
    supports_backend_process_tracking: int
    runtime_processes: list[BackendProcessIdentity]


class DatabasePluginsProtocol(Protocol):
    fernet: tuple[Fernet, ...]

    @property
    def clone_transactions(self) -> DatabasePluginCloneTransactionsProtocol: ...

    async def create_uploading_placeholder(self, plugin_name: str) -> bool: ...

    async def add_or_update_plugin(
        self,
        plugin_data: JSONDict,
        *,
        state: str | None = None,
        incompatibility: CompatibilityInfo | None = None,
        override: bool | None = None,
    ) -> None: ...

    async def mark_as_absent(self, plugin_names: list[str]) -> None: ...

    async def get_all_listable_plugins(self, plugin_name: str | None = None) -> list[JSONDict]: ...

    async def get_all_plugins(self) -> list[JSONDict]: ...

    async def get_latest_plugin_usage(self) -> JSONDict | None: ...

    async def get_system_setting(self, key: str) -> JSONValue | None: ...

    async def set_system_setting(
        self,
        key: str,
        value: JSONValue,
    ) -> None: ...

    async def mark_welcome_message_logged(self, plugin_name: str) -> None: ...

    async def mark_plugin_user_enabled_once(self, plugin_name: str) -> None: ...

    async def get_plugin_by_name(self, plugin_name: str) -> JSONDict | None: ...

    async def get_plugin_state(self, plugin_name: str) -> str | None: ...

    async def get_backend_variant_id(self, plugin_name: str) -> str | None: ...

    async def set_backend_variant_id(
        self,
        plugin_name: str,
        backend_variant_id: str,
    ) -> None: ...

    async def update_backend_variant_available_count(
        self,
        plugin_name: str,
        expected_state: str,
        available_count: int,
    ) -> bool: ...

    async def update_plugin_state(
        self,
        plugin_name: str,
        state: str,
    ) -> None: ...

    async def permanently_delete_plugin_record(self, plugin_name: str) -> int: ...

    async def clear_incompatibility(
        self,
        plugin_name: str,
    ) -> None: ...

    async def update_plugin_runtime_loaded(
        self,
        plugin_name: str,
        runtime_loaded: bool,
    ) -> None: ...

    async def set_incompatibility_override(
        self,
        plugin_name: str,
        override: bool,
    ) -> None: ...

    async def update_plugin_catalog_metadata(
        self,
        plugin_name: str,
        *,
        parameter_schema: JSONDict | None = None,
        backend_variant_options: list[JSONDict] | None = None,
    ) -> None: ...

    async def set_incompatibility(
        self,
        plugin_name: str,
        info: CompatibilityInfo,
        state: str | None = None,
    ) -> None: ...

    async def get_all_external_providers(self) -> list[JSONDict]: ...

    async def get_external_provider(
        self,
        provider_id: str,
        *,
        decrypt_key: bool = False,
    ) -> ExternalProviderInternalRecord | None: ...

    async def list_providers_for_plugin(
        self,
        plugin_name: str,
    ) -> list[ExternalProviderInternalRecord]: ...

    async def mutate_update_provider(
        self,
        request: ProviderUpdateMutationRequest,
    ) -> ProviderMutationOutcome: ...

    async def mutate_create_provider(
        self,
        request: ProviderCreateMutationRequest,
    ) -> ProviderMutationOutcome: ...

    async def mutate_delete_provider(
        self,
        request: ProviderDeleteMutationRequest,
    ) -> ProviderMutationOutcome: ...

    async def read_provider_mutation_outcome(
        self,
        request: ProviderMutationReplayRequest,
    ) -> ProviderMutationOutcome | None: ...

    async def upsert_plugin_managed_provider(
        self,
        plugin_name: str,
        provider_id: str,
        name: str,
        url: str,
    ) -> ExternalProviderInternalRecord | None: ...

    async def get_stats_for_plugins(self, plugin_names: list[str]) -> dict[str, dict[str, int]]: ...

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None: ...

    async def get_all_circuit_breaker_states(self) -> list[JSONDict]: ...

    async def upsert_circuit_breaker_state(
        self,
        plugin_name: str,
        state: CircuitBreakerStatePayload,
    ) -> None: ...

    async def get_runtime_processes(self, plugin_name: str) -> list[BackendProcessIdentity]: ...

    async def set_runtime_processes(
        self,
        plugin_name: str,
        identities: list[BackendProcessIdentity],
    ) -> None: ...

    async def clear_runtime_processes(self, plugin_name: str) -> None: ...

    async def list_plugins_with_runtime_processes(self) -> list[PluginRuntimeProcessesPayload]: ...
