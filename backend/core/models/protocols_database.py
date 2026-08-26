"""SoAI - Model database protocols [backend/core/models/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.orchestrator.routing_config import VirtualModelConfig
    from core.plugins.protocols_lifecycle import PluginLifecycleProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("DatabaseModelsProtocol", "ModelDatabasePurgeServiceProtocol")


class DatabaseModelsProtocol(Protocol):
    async def get_all_models_by_plugin(
        self,
    ) -> dict[str, dict[str, JSONDict]]: ...

    async def get_models_info(self, universal_ids: list[str]) -> dict[str, JSONDict]: ...

    async def get_model_info(self, universal_id: str) -> JSONDict | None: ...

    async def find_virtual_models_using_universal_ids(
        self,
        universal_ids: list[str],
    ) -> dict[str, list[str]]: ...

    async def list_all_virtual_models(self) -> list[VirtualModelConfig]: ...

    async def add_or_update_virtual_model(self, virtual_model: VirtualModelConfig) -> None: ...

    async def delete_virtual_model(self, name: str) -> bool: ...

    async def upsert_models(self, models: list[JSONDict]) -> None: ...

    async def set_model_status_for_plugin(
        self,
        plugin_name: str,
        status: str,
    ) -> tuple[int, list[str]]: ...

    async def get_parameter_version(self, universal_id: str) -> int: ...

    async def get_model_custom_parameters(self, universal_id: str) -> JSONDict: ...

    async def update_model_parameters(
        self,
        universal_id: str,
        parameters: dict[str, JSONValue],
    ) -> bool: ...

    async def increment_parameter_version(self, universal_id: str) -> int: ...

    async def update_model_alias(self, universal_id: str, updates: JSONDict) -> bool: ...

    async def update_model_enabled(self, universal_id: str, enabled: bool) -> bool: ...

    async def record_model_usage(
        self,
        universal_id: str,
        plugin_name: str,
    ) -> tuple[int, int] | None: ...

    async def get_latest_model_usage(self) -> JSONDict | None: ...

    async def update_model_openai_capabilities_overrides(
        self,
        universal_id: str,
        overrides: JSONDict | None,
    ) -> bool: ...

    async def get_virtual_model(self, name: str) -> VirtualModelConfig | None: ...

    async def list_model_rows(self) -> list[JSONDict]: ...

    async def get_universal_ids_with_custom_parameters(
        self,
        universal_ids: list[str],
    ) -> list[str]: ...

    async def purge_models_for_plugin(self, plugin_name: str) -> bool: ...

    async def resolve_by_plugin_and_source_model_id(
        self,
        plugin_name: str,
        source_model_id: str,
    ) -> str | None: ...

    async def resolve_by_provider_and_source_model_id(
        self,
        provider_canonical_name: str,
        source_model_id: str,
    ) -> str | None: ...

    async def delete_models_by_id(self, universal_id: str) -> bool: ...

    async def delete_models_by_ids(self, universal_ids: list[str]) -> int: ...


class ModelDatabasePurgeServiceProtocol(Protocol):
    async def purge_models_for_plugin(
        self,
        plugin_name: str,
        plugin_lifecycle: PluginLifecycleProtocol,
    ) -> bool: ...
