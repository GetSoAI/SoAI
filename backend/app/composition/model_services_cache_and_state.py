"""SoAI - Model services cache and mutable state assembly [backend/app/composition/model_services_cache_and_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.config.numeric import coerce_positive_int
from models.parameters.cache import AsyncParameterCache

__all__ = (
    "InstalledPluginNamesState",
    "build_model_record_locks",
    "build_model_service_caches",
)


class InstalledPluginNamesState:
    def __init__(self) -> None:
        self._names: set[str] = set()

    def ref(self) -> set[str]:
        return self._names

    def set_names(self, names: set[str]) -> None:
        self._names = names


def build_model_service_caches(
    ms_cache_config: dict[str, int | float | str | bool | None],
) -> tuple[
    asyncio.Lock,
    TTLCache[str, str],
    AsyncParameterCache,
]:
    resolution_cache_lock: asyncio.Lock = asyncio.Lock()
    resolution_cache: TTLCache[str, str] = TTLCache(
        TTLCacheDependencies(
            ttl_seconds=coerce_positive_int(
                ms_cache_config.get("RESOLUTION_TTL_SEC", 300),
                default=300,
                minimum=1,
            ),
            max_size=coerce_positive_int(
                ms_cache_config.get("RESOLUTION_MAX_SIZE", 5000),
                default=5000,
                minimum=1,
            ),
        ),
    )
    parameter_cache = AsyncParameterCache(
        max_size=coerce_positive_int(
            ms_cache_config.get("PARAMETER_MAX_SIZE", 2000),
            default=2000,
            minimum=1,
        ),
    )
    return (resolution_cache_lock, resolution_cache, parameter_cache)


def build_model_record_locks() -> TTLAsyncLockRegistry[str]:
    return TTLAsyncLockRegistry(
        TTLAsyncLockRegistryDependencies(
            ttl_seconds=3600.0,
            max_size=2000,
            cleanup_interval_seconds=300.0,
        ),
    )
