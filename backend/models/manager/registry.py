"""SoAI - Model registry and plugin metadata caching [backend/models/manager/registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.models.protocols_database import DatabaseModelsProtocol
from core.plugins.name_validation import require_plugin_name
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.types.json import is_json_value
from models.manager.capabilities import derive_model_type, normalize_plugin_record

if TYPE_CHECKING:
    from core.models.external_provider_record import ExternalProviderInternalRecord
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ModelRegistry",
    "ModelRegistryDependencies",
)

LOGGER_NAME = "SoAI.models.manager.registry"
OPERATION = "model_manager.get_plugin_info"


@dataclass(frozen=True, slots=True)
class ModelRegistryDependencies:
    database_models: DatabaseModelsProtocol
    database_plugins: DatabasePluginsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelRegistryDependencies",
            database_models=self.database_models,
            database_plugins=self.database_plugins,
        )


class ModelRegistry:
    def __init__(self, deps: ModelRegistryDependencies) -> None:
        self._deps = deps
        self._plugin_info_cache: dict[str, JSONDict | None] = {}
        self._plugin_info_cache_lock = asyncio.Lock()

    async def model_get_info(self, universal_id: str) -> JSONDict | None:
        raw_model_info = await self._deps.database_models.get_model_info(universal_id)
        model_info = _ensure_json_dict(raw_model_info)
        if not model_info:
            return None
        plugin_name_value = model_info.get("plugin")
        if (
            isinstance(plugin_name_value, str)
            and plugin_name_value
            and (plugin_info := await self.get_plugin_info(plugin_name_value))
            and (model_type := derive_model_type(model_info, plugin_info))
        ):
            model_info["model_type"] = model_type
        return model_info

    async def get_external_provider_for_model(
        self,
        universal_id: str,
    ) -> ExternalProviderInternalRecord | None:
        if (model_info := await self.model_get_info(universal_id)) and (
            provider_id := model_info.get("provider_id")
        ):
            if not isinstance(provider_id, str) or not provider_id:
                return None
            provider = await self._deps.database_plugins.get_external_provider(
                provider_id,
                decrypt_key=True,
            )
            return provider
        return None

    async def provider_get_external(
        self,
        provider_id: str,
        decrypt_key: bool = False,
    ) -> ExternalProviderInternalRecord | None:
        if not provider_id:
            raise ValidationError("provider_id is required.")
        provider = await self._deps.database_plugins.get_external_provider(
            provider_id,
            decrypt_key=decrypt_key,
        )
        return provider

    async def provider_list_for_plugin(
        self,
        plugin_name: str,
    ) -> list[ExternalProviderInternalRecord]:
        normalized_plugin_name = require_plugin_name(plugin_name)
        providers = await self._deps.database_plugins.list_providers_for_plugin(
            normalized_plugin_name,
        )
        return [provider for provider in providers if provider]

    async def update_provider_status(
        self,
        provider_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        if not provider_id:
            raise ValidationError("provider_id is required.")
        if not status:
            raise ValidationError("status is required.")
        await self._deps.database_plugins.update_provider_status(provider_id, status, error)

    async def upsert_plugin_managed_provider(
        self,
        plugin_name: str,
        provider_id: str,
        name: str,
        url: str,
    ) -> ExternalProviderInternalRecord | None:
        normalized_plugin_name = require_plugin_name(plugin_name)
        if not provider_id:
            raise ValidationError("provider_id is required.")
        if not name:
            raise ValidationError("name is required.")
        if not url:
            raise ValidationError("url is required.")
        provider = await self._deps.database_plugins.upsert_plugin_managed_provider(
            normalized_plugin_name,
            provider_id,
            name,
            url,
        )
        return provider

    async def get_plugin_info(self, plugin_name: str) -> JSONDict | None:
        logger = get_logger(LOGGER_NAME)
        if not plugin_name:
            return None
        async with self._plugin_info_cache_lock:
            if plugin_name in self._plugin_info_cache:
                cached = self._plugin_info_cache[plugin_name]
                return dict(cached) if cached else None
        try:
            fetched = await self._deps.database_plugins.get_plugin_by_name(plugin_name)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to fetch plugin info from database (non-critical).",
                operation=OPERATION,
                details={"plugin_name": plugin_name},
                level="debug",
            )
            fetched = None
        normalized = (
            normalize_plugin_record(normalized_record)
            if (normalized_record := _ensure_json_dict(fetched))
            else None
        )
        async with self._plugin_info_cache_lock:
            self._plugin_info_cache[plugin_name] = normalized
        return dict(normalized) if normalized else None

    async def clear_plugin_info_cache(self) -> None:
        async with self._plugin_info_cache_lock:
            self._plugin_info_cache.clear()


def _ensure_json_dict(data: Mapping[str, JSONValue] | None) -> JSONDict | None:
    if data is None:
        return None
    normalized: JSONDict = {}
    for key, value in data.items():
        if not isinstance(key, str):
            continue
        if not is_json_value(value):
            raise ValidationError("Database record contains non-JSON value.")
        normalized[key] = value
    return normalized
