"""SoAI - TTL-bounded DNS resolution cache [backend/core/network/dns_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
import time

__all__ = ("DnsResolutionCache",)


class DnsResolutionCache:
    __slots__ = ("_cache", "_lock", "_max_entries", "_ttl_seconds")

    def __init__(self, *, ttl_seconds: float = 60.0, max_entries: int = 1024) -> None:
        self._cache: dict[tuple[str, int], tuple[float, tuple[str, ...]]] = {}
        self._lock: threading.Lock = threading.Lock()
        self._ttl_seconds: float = ttl_seconds
        self._max_entries: int = max_entries

    def get(self, host: str, port: int) -> tuple[str, ...] | None:
        key = (host, port)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            cached_at, resolved_ips = entry
            if time.monotonic() - cached_at > self._ttl_seconds:
                self._cache.pop(key, None)
                return None
            return resolved_ips

    def put(self, host: str, port: int, resolved_ips: tuple[str, ...]) -> None:
        key = (host, port)
        with self._lock:
            if len(self._cache) >= self._max_entries and key not in self._cache:
                self._evict_expired()
                if len(self._cache) >= self._max_entries:
                    oldest_key = min(self._cache, key=lambda cache_key: self._cache[cache_key][0])
                    del self._cache[oldest_key]
            self._cache[key] = (time.monotonic(), resolved_ips)

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired_keys = [
            key
            for key, (cached_at, _) in self._cache.items()
            if now - cached_at > self._ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]
