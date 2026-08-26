"""SoAI - Path subtree async lock for filesystem mutations [backend/core/concurrency/path_tree_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass

from core.errors.exceptions import ValidationError

__all__ = (
    "AsyncPathTreeLock",
    "normalize_filesystem_lock_path",
)


def normalize_filesystem_lock_path(path: str) -> str:
    if not path:
        raise ValidationError("Lock path must be provided.")
    normalized = os.path.normcase(os.path.normpath(path))
    normalized = normalized.replace("\\", "/")
    if len(normalized) == 3 and normalized[1] == ":" and normalized[2] == "/":
        return normalized
    if normalized.endswith("/") and len(normalized) > 1:
        normalized = normalized.rstrip("/")
        if not normalized:
            return "/"
    return normalized


def _is_ancestor_or_self(*, ancestor: str, path: str) -> bool:
    if ancestor == path:
        return True
    if ancestor == "/":
        return path.startswith("/")
    if ancestor.endswith("/"):
        return path.startswith(ancestor)
    return path.startswith(f"{ancestor}/")


@dataclass(slots=True)
class _HeldPathLock:
    owner_task_id: int | None
    depth: int


class AsyncPathTreeLock:
    __slots__ = ("_condition", "_held")

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._held: dict[str, _HeldPathLock] = {}

    @asynccontextmanager
    async def lock(self, path: str) -> AsyncGenerator[None]:
        async with self.lock_many((path,)):
            yield

    @asynccontextmanager
    async def lock_many(self, paths: Iterable[str]) -> AsyncGenerator[None]:
        keys = [normalize_filesystem_lock_path(path) for path in paths]
        keys = sorted(set(keys))
        if not keys:
            raise ValidationError("At least one lock path must be provided.")
        acquired: list[str] = []
        try:
            for key in keys:
                await self._acquire_one(key)
                acquired.append(key)
            yield
        finally:
            for key in reversed(acquired):
                await self._release_one(key)

    async def _acquire_one(self, key: str) -> None:
        current_task = asyncio.current_task()
        current_task_id = id(current_task) if current_task is not None else None
        async with self._condition:
            existing = self._held.get(key)
            if existing is not None and existing.owner_task_id == current_task_id:
                existing.depth += 1
                return
            while True:
                conflicts = False
                for held_key, held_entry in self._held.items():
                    if held_entry.owner_task_id == current_task_id:
                        continue
                    if _is_ancestor_or_self(ancestor=held_key, path=key) or _is_ancestor_or_self(
                        ancestor=key,
                        path=held_key,
                    ):
                        conflicts = True
                        break
                if not conflicts:
                    self._held[key] = _HeldPathLock(owner_task_id=current_task_id, depth=1)
                    return
                await self._condition.wait()

    async def _release_one(self, key: str) -> None:
        current_task = asyncio.current_task()
        current_task_id = id(current_task) if current_task is not None else None
        async with self._condition:
            held = self._held.get(key)
            if held is None:
                raise ValidationError("Attempted to release an unheld lock.")
            if held.owner_task_id != current_task_id:
                raise ValidationError("Attempted to release a lock owned by another task.")
            held.depth = max(0, int(held.depth) - 1)
            if held.depth:
                return
            self._held.pop(key, None)
            self._condition.notify_all()
