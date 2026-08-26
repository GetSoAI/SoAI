"""SoAI - TTL cache primitive [backend/core/concurrency/ttl_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError

__all__ = (
    "TTLCache",
    "TTLCacheDependencies",
)


@dataclass(frozen=True, slots=True)
class TTLCacheDependencies:
    ttl_seconds: float
    max_size: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="TTLCacheDependencies",
            max_size=self.max_size,
            ttl_seconds=self.ttl_seconds,
        )
        if self.ttl_seconds <= 0:
            raise ValidationError("ttl_seconds must be greater than zero.")
        if self.max_size <= 0:
            raise ValidationError("max_size must be greater than zero.")


class TTLCache[K: Hashable, V]:
    def __init__(self, deps: TTLCacheDependencies) -> None:
        self._ttl = float(deps.ttl_seconds)
        self._max_size = int(deps.max_size)
        self._store: OrderedDict[K, tuple[V, float]] = OrderedDict()
        self._lock = threading.Lock()

    def _is_expired(self, timestamp: float) -> bool:
        return time.monotonic() - timestamp >= self._ttl

    def _evict_until_within_limit(self) -> None:
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def get(self, key: K) -> V | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, timestamp = entry
            if self._is_expired(timestamp):
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return value

    def put(self, key: K, value: V) -> None:
        now = time.monotonic()
        with self._lock:
            if key in self._store:
                self._store.pop(key)
            self._store[key] = (value, now)
            self._store.move_to_end(key)
            self._evict_until_within_limit()

    def delete(self, key: K) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def delete_matching(self, predicate: Callable[[K, V], bool]) -> set[K]:
        removed_keys: set[K] = set()
        with self._lock:
            for key, (value, timestamp) in list(self._store.items()):
                if self._is_expired(timestamp):
                    self._store.pop(key, None)
                    removed_keys.add(key)
                    continue
                if predicate(key, value):
                    self._store.pop(key, None)
                    removed_keys.add(key)
        return removed_keys

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
