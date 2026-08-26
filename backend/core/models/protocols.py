"""SoAI - Protocol definitions for model management and database operations [backend/core/models/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.database.provider_mutation_requests import (
        ProviderCreateMutationRequest,
        ProviderDeleteMutationRequest,
        ProviderMutationOutcome,
        ProviderMutationReplayRequest,
        ProviderUpdateMutationRequest,
    )
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.orchestrator.routing_config import (
        ConstituentModelConfig,
        VirtualModelConfig,
    )
    from core.runtime.startup_status import StartupPhaseResult
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ModelDiscoveryServiceProtocol",
    "ModelInformationServiceProtocol",
    "ModelManagerProtocol",
    "ModelParameterServiceProtocol",
    "ModelProviderCoordinatorProtocol",
    "ModelRegistryProtocol",
    "ModelResolutionServiceProtocol",
    "ParameterManagerProtocol",
    "VirtualModelServiceProtocol",
)


class ModelRegistryProtocol(Protocol):

    async def model_get_info(self, universal_id: str) -> JSONDict | None: ...

    async def get_plugin_info(self, plugin_name: str) -> JSONDict | None: ...

    async def clear_plugin_info_cache(self) -> None: ...

    async def get_external_provider_for_model(
        self,
        universal_id: str,
    ) -> ExternalProviderInternalRecord | None: ...

    async def provider_get_external(
        self,
        provider_id: str,
        decrypt_key: bool = False,
    ) -> ExternalProviderInternalRecord | None: ...

    async def provider_list_for_plugin(
        self,
        plugin_name: str,
    ) -> list[ExternalProviderInternalRecord]: ...

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None: ...

    async def upsert_plugin_managed_provider(
        self,
        plugin_name: str,
        provider_id: str,
        name: str,
        url: str,
    ) -> ExternalProviderInternalRecord | None: ...


class ParameterManagerProtocol(Protocol):

    async def initialize(self) -> None: ...

    async def register_plugin_parameters(self, plugin_name: str, schema: JSONDict) -> None: ...

    async def unregister_plugin_parameters(self, plugin_name: str) -> None: ...

    async def classify_parameters(
        self,
        plugin_name: str,
        parameters: JSONDict,
    ) -> tuple[JSONDict, JSONDict]: ...

    async def get_all_parameters_for_plugin(self, plugin_name: str) -> JSONDict: ...

    async def get_parameter_schema_snapshot(
        self,
        plugin_name: str,
    ) -> tuple[JSONDict, JSONDict]: ...


class ModelProviderCoordinatorProtocol(Protocol):
    async def provider_add_external_v1(
        self,
        request: ProviderCreateMutationRequest,
    ) -> tuple[ProviderMutationOutcome, ExternalProviderInternalRecord | None]: ...

    async def provider_get_external(
        self,
        provider_id: str,
        decrypt_key: bool = False,
    ) -> ExternalProviderInternalRecord | None: ...

    async def provider_list_for_plugin(
        self,
        plugin_name: str,
    ) -> list[ExternalProviderInternalRecord]: ...

    async def provider_update_external_v1(
        self,
        request: ProviderUpdateMutationRequest,
    ) -> tuple[ProviderMutationOutcome, ExternalProviderInternalRecord | None]: ...

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None: ...

    async def provider_delete_external_v1(
        self,
        request: ProviderDeleteMutationRequest,
    ) -> ProviderMutationOutcome: ...

    async def provider_read_mutation_outcome(
        self,
        request: ProviderMutationReplayRequest,
    ) -> tuple[ProviderMutationOutcome, ExternalProviderInternalRecord | None] | None: ...


class ModelDiscoveryServiceProtocol(Protocol):

    @property
    def startup_discovery_complete_event(self) -> asyncio.Event: ...

    @property
    def startup_discovery_result(self) -> StartupPhaseResult: ...

    async def model_run_startup_discovery(self) -> None: ...

    async def model_background_refresh_loop(self, refresh_interval_ms: int) -> None: ...

    async def model_discover_all(
        self,
        plugins_to_scan: list[str] | None = None,
        *,
        wait_for_completion: bool = False,
    ) -> None: ...


class ModelResolutionServiceProtocol(Protocol):

    async def model_resolve_to_universal_id(self, name_or_alias: str) -> str | None: ...

    async def model_check_exists(self, universal_id: str) -> bool: ...

    async def model_invalidate_resolution_cache(self) -> None: ...

    def model_get_installed_plugin_names(self) -> list[str]: ...


class ModelInformationServiceProtocol(Protocol):

    async def model_get_info(self, universal_id: str) -> JSONDict | None: ...

    async def model_get_info_batch(self, universal_ids: list[str]) -> dict[str, JSONDict]: ...

    async def model_get_openai_formatted_list(self) -> JSONDict: ...

    async def model_get_available(self) -> list[JSONDict]: ...

    async def model_get_openai_formatted(
        self,
        model_id: str,
        model_resolve_to_universal_id: Callable[[str], Awaitable[str | None]],
    ) -> JSONDict | None: ...

    async def model_get_formatted_parameters(self, universal_id: str) -> JSONDict: ...

    async def model_get_plugin_capability_profile(self, plugin_name: str) -> JSONDict: ...

    async def model_invalidate_list_caches(self) -> None: ...

    async def model_get_formatted_list(self) -> dict[str, list[JSONDict]]: ...

    async def model_resolve_context_window(
        self,
        universal_id: str,
        *,
        model_info: JSONDict | None = None,
        provider_record: ExternalProviderInternalRecord | JSONDict | None = None,
        provider_record_resolved: bool = False,
    ) -> int | None: ...


class ModelParameterServiceProtocol(Protocol):

    async def model_get_parameters_and_version(self, universal_id: str) -> tuple[JSONDict, int]: ...

    async def model_get_parameter_definitions(self, universal_id: str) -> JSONDict: ...

    async def model_validate_parameters(
        self,
        universal_id: str,
        parameters: dict[str, JSONValue],
    ) -> None: ...

    async def model_validate_parameter_keys_exist(
        self,
        universal_id: str,
        keys: list[str],
    ) -> None: ...


class VirtualModelServiceProtocol(Protocol):

    def virtual_model_get(self, name: str) -> VirtualModelConfig | None: ...

    async def virtual_model_validate_constituents(
        self,
        models: list[ConstituentModelConfig],
    ) -> None: ...

    async def virtual_model_add(
        self,
        virtual_model_config: VirtualModelConfig,
    ) -> VirtualModelConfig: ...

    async def virtual_model_update(self, name: str, updates: JSONDict) -> VirtualModelConfig: ...

    async def virtual_model_set_enabled(self, name: str, enabled: bool) -> VirtualModelConfig: ...

    async def virtual_model_delete(self, name: str) -> bool: ...


class ModelManagerProtocol(Protocol):

    shutdown_event: asyncio.Event
    model_services_ready_event: asyncio.Event

    @property
    def startup_discovery_complete_event(self) -> asyncio.Event: ...

    @property
    def startup_discovery_result(self) -> StartupPhaseResult: ...

    async def initialize(self) -> None: ...

    async def shutdown(self) -> None: ...
