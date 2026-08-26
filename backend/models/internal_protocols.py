"""SoAI - Models subsystem internal protocols [backend/models/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

from core.events.types_base import Event

if TYPE_CHECKING:
    from core.events.types_models_model_commands import ModelDeleteCommand
    from core.events.types_plugins import PurgeModelsForPluginCommand
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.state.protocols import StateAggregatorProtocol
    from core.types.json import JSONDict

__all__ = (
    "AsyncParameterCacheProtocol",
    "CacheInvalidator",
    "ConstituentModelValidatorProtocol",
    "InstalledPluginNamesAccessor",
    "ModelActionsServiceProtocol",
    "ModelFingerprintServiceProtocol",
    "ModelMutationEffectsProtocol",
    "ModelParameterMutationServiceProtocol",
    "MutationCallable",
    "RoutingPublisher",
    "VirtualModelCoordinatorProtocol",
)


class ModelActionsServiceProtocol(Protocol):
    async def modelhandle_delete_command(self, command: ModelDeleteCommand) -> None: ...

    async def model_handle_purge_for_plugin_command(
        self,
        command: PurgeModelsForPluginCommand,
    ) -> None: ...

    async def model_update_alias(
        self,
        universal_id: str,
        name: str | None,
        desc: str | None = None,
    ) -> None: ...

    async def model_delete_alias(self, universal_id: str) -> None: ...

    async def model_update_enabled(self, universal_id: str, enabled: bool) -> None: ...

    async def model_update_openai_capability_override(
        self,
        universal_id: str,
        category: str,
        token: str,
        enabled: bool,
    ) -> None: ...

    async def model_reset_openai_capability_overrides(self, universal_id: str) -> None: ...

    async def model_purge_for_plugin(self, plugin_name: str) -> bool: ...


class AsyncParameterCacheProtocol(Protocol):
    async def get(self, key: str) -> tuple[JSONDict, int] | None: ...

    async def put(self, key: str, value: JSONDict, version: int) -> None: ...

    async def invalidate(self, key: str) -> None: ...


class MutationCallable(Protocol):
    def __call__(self, schema: JSONDict, old: JSONDict) -> tuple[JSONDict, bool, str] | None: ...


class ModelParameterMutationServiceProtocol(Protocol):
    async def start(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def enqueue_update(
        self,
        universal_id: str,
        parameters: JSONDict,
        reply_channel: asyncio.Queue[Event],
    ) -> None: ...

    async def enqueue_delete(
        self,
        universal_id: str,
        keys: list[str],
        reply_channel: asyncio.Queue[Event],
    ) -> None: ...

    async def mutate(
        self,
        universal_id: str,
        *,
        metric_key: str,
        metric_value: int | None = None,
        mutation: MutationCallable,
        order: int | None = None,
    ) -> None: ...


class ModelMutationEffectsProtocol(Protocol):
    async def publish_catalog_changed(
        self,
        *,
        added_universal_ids: list[str] | None = None,
        removed_universal_ids: list[str] | None = None,
    ) -> None: ...

    async def invalidate_all_resolution_cache(self) -> None: ...

    async def invalidate_resolution_cache_for_model(self, universal_id: str) -> None: ...

    async def invalidate_parameter_cache_for_models(self, universal_ids: list[str]) -> None: ...

    async def finalize_model_deletion(self, universal_id: str) -> None: ...

    async def commit_parameter_changes(
        self,
        *,
        universal_id: str,
        plugin_name: str,
        new_custom: JSONDict,
        reload_needed: bool,
        reload_reason: str,
    ) -> None: ...


class CacheInvalidator(Protocol):
    async def __call__(self) -> None: ...


class RoutingPublisher(Protocol):
    async def __call__(self) -> None: ...


class InstalledPluginNamesAccessor(Protocol):
    def __call__(self) -> set[str]: ...


class VirtualModelCoordinatorProtocol(Protocol):
    async def virtual_model_add(
        self,
        config: VirtualModelConfig,
        validate_callback: Callable[[VirtualModelConfig], Awaitable[None]],
    ) -> VirtualModelConfig: ...

    async def virtual_model_update(
        self,
        name: str,
        updates: JSONDict,
        validate_callback: Callable[[VirtualModelConfig], Awaitable[None]],
    ) -> VirtualModelConfig: ...

    async def virtual_model_set_enabled(self, name: str, enabled: bool) -> VirtualModelConfig: ...

    async def virtual_model_delete(self, name: str) -> bool: ...


class ConstituentModelValidatorProtocol(Protocol):
    state_aggregator: StateAggregatorProtocol

    async def model_get_info_batch(self, universal_ids: list[str]) -> dict[str, JSONDict]: ...

    async def model_validate_parameters(self, universal_id: str, parameters: JSONDict) -> None: ...


class ModelFingerprintServiceProtocol(Protocol):
    def model_fingerprint_records(self, records: list[JSONDict]) -> str | None: ...
