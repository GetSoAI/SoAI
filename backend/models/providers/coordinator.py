"""SoAI - Provider coordinator for external provider operations [backend/models/providers/coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.database.provider_mutation_requests import (
    ProviderCreateMutationRequest,
    ProviderDeleteMutationRequest,
    ProviderMutationOutcome,
    ProviderMutationReplayRequest,
    ProviderUpdateMutationRequest,
)
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.models.external_provider_record import coerce_external_provider_internal_record
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.serialization.json_parsing import parse_json_dict

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord

__all__ = (
    "ModelProviderCoordinator",
    "ModelProviderCoordinatorDependencies",
)


@dataclass(frozen=True, slots=True)
class ModelProviderCoordinatorDependencies:
    database: DatabasePluginsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelProviderCoordinatorDependencies",
            database=self.database,
        )


class ModelProviderCoordinator:

    def __init__(self, deps: ModelProviderCoordinatorDependencies) -> None:
        self._deps = deps

    @staticmethod
    def _provider_from_outcome(
        outcome: ProviderMutationOutcome,
    ) -> ExternalProviderInternalRecord | None:
        if outcome.provider_json is None:
            return None
        return coerce_external_provider_internal_record(
            parse_json_dict(outcome.provider_json, field="provider_mutation_outcome"),
            label="Provider mutation outcome",
        )

    async def provider_add_external_v1(
        self,
        request: ProviderCreateMutationRequest,
    ) -> tuple[ProviderMutationOutcome, ExternalProviderInternalRecord | None]:
        plugin_info = await self._deps.database.get_plugin_by_name(request.plugin_name)
        if not plugin_info:
            raise ValidationError(f"Plugin '{request.plugin_name}' not found.")
        outcome = await self._deps.database.mutate_create_provider(request)
        return (outcome, self._provider_from_outcome(outcome))

    async def provider_get_external(
        self,
        provider_id: str,
        decrypt_key: bool = False,
    ) -> ExternalProviderInternalRecord | None:
        provider = await self._deps.database.get_external_provider(
            provider_id,
            decrypt_key=decrypt_key,
        )
        return provider

    async def provider_list_for_plugin(
        self,
        plugin_name: str,
    ) -> list[ExternalProviderInternalRecord]:
        providers = await self._deps.database.list_providers_for_plugin(plugin_name)
        return [provider for provider in providers if provider]

    async def provider_update_external_v1(
        self,
        request: ProviderUpdateMutationRequest,
    ) -> tuple[ProviderMutationOutcome, ExternalProviderInternalRecord | None]:
        outcome = await self._deps.database.mutate_update_provider(request)
        return (outcome, self._provider_from_outcome(outcome))

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        await self._deps.database.update_provider_status(provider_id, status, error)

    async def provider_delete_external_v1(
        self,
        request: ProviderDeleteMutationRequest,
    ) -> ProviderMutationOutcome:
        return await self._deps.database.mutate_delete_provider(request)

    async def provider_read_mutation_outcome(
        self,
        request: ProviderMutationReplayRequest,
    ) -> tuple[ProviderMutationOutcome, ExternalProviderInternalRecord | None] | None:
        outcome = await self._deps.database.read_provider_mutation_outcome(request)
        if outcome is None:
            return None
        return (outcome, self._provider_from_outcome(outcome))
