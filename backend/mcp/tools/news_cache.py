"""SoAI - MCP news response cache [backend/mcp/tools/news_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.singleflight import AsyncSingleflight
from core.concurrency.ttl_cache import TTLCache, TTLCacheDependencies
from mcp.tools.news_payload import NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("NewsResponseCache",)

_DEFAULT_DOC_TTL_SECONDS = 300.0
_DEFAULT_FALLBACK_TTL_SECONDS = 60.0
_DEFAULT_MAX_ENTRIES = 64


def _new_singleflight() -> AsyncSingleflight[str, JSONDict]:
    return AsyncSingleflight()


@dataclass(slots=True)
class NewsResponseCache:
    doc_ttl_seconds: float = _DEFAULT_DOC_TTL_SECONDS
    fallback_ttl_seconds: float = _DEFAULT_FALLBACK_TTL_SECONDS
    max_entries: int = _DEFAULT_MAX_ENTRIES
    singleflight: AsyncSingleflight[str, JSONDict] = field(default_factory=_new_singleflight)
    doc_entries: TTLCache[str, JSONDict] = field(init=False)
    fallback_entries: TTLCache[str, JSONDict] = field(init=False)

    def __post_init__(self) -> None:
        self.doc_entries = TTLCache(
            TTLCacheDependencies(
                ttl_seconds=self.doc_ttl_seconds,
                max_size=self.max_entries,
            ),
        )
        self.fallback_entries = TTLCache(
            TTLCacheDependencies(
                ttl_seconds=self.fallback_ttl_seconds,
                max_size=self.max_entries,
            ),
        )

    async def get(self, key: str) -> JSONDict | None:
        exact = self.doc_entries.get(key)
        if exact is not None:
            return exact
        return self.fallback_entries.get(key)

    async def put(self, key: str, payload: JSONDict) -> None:
        if payload.get("search_mode") == NEWS_SEARCH_MODE_HEADLINE_SUMMARY_GLOBAL:
            self.fallback_entries.put(key, payload)
            return
        self.doc_entries.put(key, payload)

    async def get_or_compute(
        self,
        key: str,
        computation: Callable[[], Awaitable[JSONDict]],
    ) -> JSONDict:
        cached = await self.get(key)
        if cached is not None:
            return cached
        return await self.singleflight.execute_or_wait(
            key,
            lambda: self._compute_and_store(key, computation),
        )

    async def _compute_and_store(
        self,
        key: str,
        computation: Callable[[], Awaitable[JSONDict]],
    ) -> JSONDict:
        cached = await self.get(key)
        if cached is not None:
            return cached
        payload = await computation()
        await self.put(key, payload)
        return payload
