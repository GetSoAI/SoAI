"""SoAI - Model resolution cache invalidation [backend/models/identification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.ttl_cache import TTLCache

__all__ = ("invalidate_resolution_cache_for_model",)


async def invalidate_resolution_cache_for_model(
    resolution_cache_lock: asyncio.Lock,
    resolution_cache: TTLCache[str, str],
    universal_id: str,
) -> None:
    async with resolution_cache_lock:

        def _matches(_key: str, value: str) -> bool:
            return value == universal_id

        resolution_cache.delete_matching(_matches)
