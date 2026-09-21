"""SoAI - Normalized URL memory cache for media previews [backend/webui/manager/media_preview_memory_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from core.network.urls import normalize_http_url

__all__ = ("NormalizedMediaPreviewCache",)

MEDIA_PREVIEW_MEMORY_CACHE_TTL_SECONDS = 300.0
MEDIA_PREVIEW_MEMORY_CACHE_MAX_SIZE = 2048


class NormalizedMediaPreviewCache[PreviewValue]:
    __slots__ = ("_cache",)

    def __init__(self) -> None:
        self._cache: TTLCache[str, PreviewValue] = TTLCache(
            TTLCacheDependencies(
                ttl_seconds=MEDIA_PREVIEW_MEMORY_CACHE_TTL_SECONDS,
                max_size=MEDIA_PREVIEW_MEMORY_CACHE_MAX_SIZE,
            ),
        )

    def lookup_source_url(self, source_url: str) -> tuple[str, PreviewValue | None]:
        normalized_url = normalize_http_url(source_url)
        return normalized_url, self.get(normalized_url)

    def get(self, normalized_url: str) -> PreviewValue | None:
        return self._cache.get(normalized_url)

    def put(self, normalized_url: str, preview: PreviewValue) -> None:
        self._cache.put(normalized_url, preview)
