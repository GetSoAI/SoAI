"""SoAI - SoAI link resolve concurrency limiter [backend/features/api/runtime/container/soai_link_resolve_limiter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Hashable
from contextlib import asynccontextmanager

from core.errors.exceptions import ValidationError

__all__ = ("SoaiLinkResolveConcurrencyLimiter",)


class SoaiLinkResolveConcurrencyLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active_counts: dict[Hashable, int] = {}

    @asynccontextmanager
    async def limit(self, *, key: Hashable, maximum: int) -> AsyncGenerator[None]:
        if maximum <= 0:
            raise ValidationError("SoAI link resolve concurrency limit must be positive.")
        await self._acquire(key=key, maximum=maximum)
        try:
            yield
        finally:
            await self._release(key)

    async def _acquire(self, *, key: Hashable, maximum: int) -> None:
        async with self._lock:
            active_count = self._active_counts.get(key, 0)
            if active_count >= maximum:
                raise ValidationError("Too many SoAI link resolve requests are already running.")
            self._active_counts[key] = active_count + 1

    async def _release(self, key: Hashable) -> None:
        async with self._lock:
            active_count = self._active_counts.get(key, 0)
            if active_count <= 1:
                self._active_counts.pop(key, None)
                return
            self._active_counts[key] = active_count - 1
