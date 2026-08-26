"""SoAI - MCP worker reindex lock registry [backend/mcp/worker/reindex_lock_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies

__all__ = ("ReindexLockRegistry", "ReindexLockRegistryDependencies")


@dataclass(frozen=True, slots=True)
class ReindexLockRegistryDependencies:
    initial_keys: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ReindexLockRegistryDependencies",
            initial_keys=self.initial_keys,
        )


class ReindexLockRegistry:
    def __init__(self, deps: ReindexLockRegistryDependencies) -> None:
        self._keys: set[str] = set(deps.initial_keys)
        self._lock = asyncio.Lock()

    async def acquire(self, lock_key: str) -> bool:
        normalized = str(lock_key or "").strip()
        if not normalized:
            return False
        async with self._lock:
            if normalized in self._keys:
                return False
            self._keys.add(normalized)
            return True

    async def release(self, lock_key: str) -> None:
        normalized = str(lock_key or "").strip()
        if not normalized:
            return
        async with self._lock:
            self._keys.discard(normalized)

    async def is_in_progress(self, lock_key: str) -> bool:
        normalized = str(lock_key or "").strip()
        if not normalized:
            return False
        async with self._lock:
            return normalized in self._keys
