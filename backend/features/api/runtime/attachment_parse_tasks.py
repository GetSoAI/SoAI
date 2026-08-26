"""SoAI - Active direct attachment parse task ownership [backend/features/api/runtime/attachment_parse_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.tasks.awaitable_cleanup import try_close_unawaited

if TYPE_CHECKING:
    from asyncio import Task
    from collections.abc import Coroutine

    from features.api.runtime.internal_protocols import (
        AttachmentParseCoroutineFactory,
        AttachmentParseTaskSpawnerProtocol,
    )

__all__ = (
    "AttachmentParseTaskRegistry",
    "AttachmentParseTaskRegistryDependencies",
)


async def _default_spawner(
    attachment_id: str,
    awaitable: Coroutine[None, None, None],
) -> Task[None]:
    return asyncio.create_task(awaitable, name=f"webui-attachment-parse:{attachment_id}")


@dataclass(frozen=True, slots=True)
class AttachmentParseTaskRegistryDependencies:
    task_spawner: AttachmentParseTaskSpawnerProtocol | None = None

    def __post_init__(self) -> None:
        require_dependencies(owner="AttachmentParseTaskRegistryDependencies")


class AttachmentParseTaskRegistry:
    def __init__(self, deps: AttachmentParseTaskRegistryDependencies) -> None:
        self._task_spawner = deps.task_spawner or _default_spawner
        self._tasks: dict[str, Task[None]] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return sum(not task.done() for task in self._tasks.values())

    async def schedule(
        self,
        attachment_id: str,
        coroutine_factory: AttachmentParseCoroutineFactory,
    ) -> Task[None]:
        async with self._lock:
            existing = self._tasks.get(attachment_id)
            if existing is not None and not existing.done():
                return existing
            if existing is not None:
                self._tasks.pop(attachment_id, None)
            parse_coroutine = self._run_owned(attachment_id, coroutine_factory)
            try:
                task = await self._task_spawner(attachment_id, parse_coroutine)
            except asyncio.CancelledError:
                try_close_unawaited(parse_coroutine)
                raise
            except HANDLED_RUNTIME_EXCEPTIONS:
                try_close_unawaited(parse_coroutine)
                raise
            self._tasks[attachment_id] = task
            return task

    async def _run_owned(
        self,
        attachment_id: str,
        coroutine_factory: AttachmentParseCoroutineFactory,
    ) -> None:
        try:
            await coroutine_factory()
        finally:
            current_task = asyncio.current_task()
            async with self._lock:
                if self._tasks.get(attachment_id) is current_task:
                    self._tasks.pop(attachment_id, None)

    async def cancel_and_wait(self, attachment_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(attachment_id)
        if task is None:
            return False
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return True
        finally:
            async with self._lock:
                if self._tasks.get(attachment_id) is task:
                    self._tasks.pop(attachment_id, None)
        return True

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = tuple(self._tasks.values())
            self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failures = [result for result in results if isinstance(result, Exception)]
        if failures:
            raise ExceptionGroup("Attachment parse task shutdown failed.", failures)
