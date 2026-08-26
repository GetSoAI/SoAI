"""SoAI - GPU info cache service [backend/hardware/gpu_info_cache_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "GPUInfoCacheService",
    "GPUInfoCacheServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class GPUInfoCacheServiceDependencies:
    cache_ttl_seconds: float = 1.0

    def __post_init__(self) -> None:
        require_dependencies(
            owner="GPUInfoCacheServiceDependencies",
            cache_ttl_seconds=self.cache_ttl_seconds,
        )


class GPUInfoCacheService:
    __slots__ = ("_cache", "_lock", "_revision", "cache_ttl")

    def __init__(self, dependencies: GPUInfoCacheServiceDependencies) -> None:
        self.cache_ttl: float = dependencies.cache_ttl_seconds
        self._cache: dict[bool, tuple[float, JSONDict]] = {}
        self._lock: threading.RLock = threading.RLock()
        self._revision = 0

    def set_cache_ttl(self, cache_ttl_seconds: float) -> None:
        with self._lock:
            self.cache_ttl = cache_ttl_seconds

    def get_cached(self, cache_key: bool, now: float) -> JSONDict | None:
        with self._lock:
            entry = self._cache.get(cache_key)
            if not entry:
                return None
            cached_time, cached_payload = entry
            if now - cached_time <= self.cache_ttl:
                return copy.deepcopy(cached_payload)
            self._cache.pop(cache_key, None)
            return None

    def get_cached_with_gpus(self, now: float) -> JSONDict | None:
        with self._lock:
            for cache_key, entry in tuple(self._cache.items()):
                cached_time, cached_payload = entry
                if now - cached_time > self.cache_ttl:
                    self._cache.pop(cache_key, None)
                    continue
                if _payload_has_gpus(cached_payload):
                    return copy.deepcopy(cached_payload)
            return None

    def set_cached(self, cache_key: bool, now: float, payload: JSONDict) -> None:
        with self._lock:
            self._cache[cache_key] = (now, copy.deepcopy(payload))

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._revision += 1

    def revision(self) -> int:
        with self._lock:
            return self._revision


def _payload_has_gpus(payload: JSONDict) -> bool:
    gpus_value = payload.get("gpus")
    return isinstance(gpus_value, list) and any(isinstance(entry, dict) for entry in gpus_value)
