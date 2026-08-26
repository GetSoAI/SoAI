"""SoAI - Cached model information list builders [backend/models/information/list_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.singleflight import AsyncSingleflight
from core.types.json_value import copy_json_dict
from models.catalog import CatalogSnapshot, build_catalog_snapshot
from models.information.openai_list_builder import build_openai_formatted_list
from models.list_formatting import build_formatted_model_list

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from models.information.dependencies import ModelInformationServiceDependencies

__all__ = ("ModelInformationListCache",)


def _shallow_copy_formatted_model_list(
    cached: dict[str, list[JSONDict]],
) -> dict[str, list[JSONDict]]:
    return {category: list(models) for category, models in cached.items()}


class ModelInformationListCache:

    def __init__(
        self,
        deps: ModelInformationServiceDependencies,
        model_get_plugin_capability_profile: Callable[[str], Awaitable[JSONDict]],
    ) -> None:
        self._deps = deps
        self._model_get_plugin_capability_profile = model_get_plugin_capability_profile
        self._openai_model_list_cache: tuple[JSONDict, int | None, int] | None = None
        self._formatted_model_list_cache: (
            tuple[dict[str, list[JSONDict]], int | None, int] | None
        ) = None
        self._cache_lock = asyncio.Lock()
        self._openai_list_revision = 0
        self._formatted_list_revision = 0
        self._openai_list_singleflight: AsyncSingleflight[str, JSONDict] = AsyncSingleflight(
            copy_json_dict,
        )
        self._formatted_list_singleflight: AsyncSingleflight[str, dict[str, list[JSONDict]]] = (
            AsyncSingleflight(_shallow_copy_formatted_model_list)
        )

    async def invalidate(self) -> None:
        async with self._cache_lock:
            self._openai_model_list_cache = None
            self._formatted_model_list_cache = None
            self._openai_list_revision += 1
            self._formatted_list_revision += 1

    async def get_openai_formatted_list(self) -> JSONDict:
        async with self._cache_lock:
            revision = self._openai_list_revision
        current_state_version = await self._deps.state_aggregator.get_state_version()
        async with self._cache_lock:
            if (
                self._openai_model_list_cache is not None
                and self._openai_model_list_cache[1] == current_state_version
                and self._openai_model_list_cache[2] == revision
            ):
                return copy_json_dict(self._openai_model_list_cache[0])
        flight_key = (
            f"openai_{current_state_version}_{revision}"
            if current_state_version is not None
            else f"openai_none_{revision}"
        )
        return await self._openai_list_singleflight.execute_or_wait(
            flight_key,
            lambda: self._build_openai_list_uncached(current_state_version, revision),
        )

    async def _build_openai_list_uncached(
        self,
        state_version: int | None,
        revision: int,
    ) -> JSONDict:
        response = await build_openai_formatted_list(
            database_models=self._deps.database_models,
            param_manager=self._deps.param_manager,
            database_plugins=self._deps.database_plugins,
            plugin_manager=self._deps.plugin_manager,
            state_aggregator=self._deps.state_aggregator,
            routing_config_holder=self._deps.routing_config_holder,
            installed_plugin_names_ref=self._deps.installed_plugin_names_ref,
            model_get_plugin_capability_profile=self._model_get_plugin_capability_profile,
        )
        async with self._cache_lock:
            if self._openai_list_revision == revision:
                self._openai_model_list_cache = (
                    response,
                    state_version,
                    revision,
                )
        return response

    async def get_formatted_list(self) -> dict[str, list[JSONDict]]:
        async with self._cache_lock:
            revision = self._formatted_list_revision
        current_state_version = await self._deps.state_aggregator.get_state_version()
        async with self._cache_lock:
            if (
                self._formatted_model_list_cache is not None
                and self._formatted_model_list_cache[1] == current_state_version
                and self._formatted_model_list_cache[2] == revision
            ):
                return _shallow_copy_formatted_model_list(self._formatted_model_list_cache[0])
        catalog_snapshot = await build_catalog_snapshot(
            database_models=self._deps.database_models,
            database_plugins=self._deps.database_plugins,
            plugin_manager=self._deps.plugin_manager,
            state_aggregator=self._deps.state_aggregator,
            routing_config_holder=self._deps.routing_config_holder,
            include_state_version=True,
        )
        snapshot_state_version = catalog_snapshot.state_version
        flight_key = (
            f"fmt_{snapshot_state_version}_{revision}"
            if snapshot_state_version is not None
            else f"fmt_none_{revision}"
        )

        async def compute_formatted_list() -> dict[str, list[JSONDict]]:
            return await self._build_formatted_list_uncached(catalog_snapshot, revision)

        return await self._formatted_list_singleflight.execute_or_wait(
            flight_key,
            compute_formatted_list,
        )

    async def _build_formatted_list_uncached(
        self,
        catalog_snapshot: CatalogSnapshot,
        revision: int,
    ) -> dict[str, list[JSONDict]]:
        result = await build_formatted_model_list(
            catalog_snapshot=catalog_snapshot,
            installed_plugin_names=self._deps.installed_plugin_names_ref(),
            database_models=self._deps.database_models,
            param_manager=self._deps.param_manager,
            get_plugin_info_cached=self._deps.model_registry.get_plugin_info,
        )
        async with self._cache_lock:
            if self._formatted_list_revision == revision:
                self._formatted_model_list_cache = (
                    result,
                    catalog_snapshot.state_version,
                    revision,
                )
        return result
