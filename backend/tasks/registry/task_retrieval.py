"""SoAI - Task registry cache and database retrieval [backend/tasks/registry/task_retrieval.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING

from tasks.registry.cache_operations import clear_task_from_caches
from tasks.registry.cache_policy import resolve_cached_task_locked, store_persisted_task
from tasks.registry.conversion import task_from_row

if TYPE_CHECKING:
    import asyncio

    from core.database.protocols_tasks import DatabaseTasksProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = (
    "retrieve_cached_task",
    "retrieve_task",
    "retrieve_tasks",
)


async def retrieve_task(
    registry: TaskRegistryLifecycleView,
    database_tasks: DatabaseTasksProtocol,
    task_id: str,
    *,
    force_refresh: bool = False,
    ensure_completion_event_fn: Callable[[str, bool], Coroutine[None, None, asyncio.Event]],
) -> Task | None:
    if not force_refresh:
        now = time.monotonic()
        async with registry.tasks_lock:
            cached_task = resolve_cached_task_locked(registry, task_id, now=now)
        if cached_task:
            if cached_task.status.is_terminal():
                await ensure_completion_event_fn(task_id, True)
            return cached_task
    row = await database_tasks.get_unified_task(task_id)
    if row is None:
        await clear_task_from_caches(registry, task_id)
        return None
    return await store_persisted_task(
        registry,
        task_from_row(registry.task_catalog, row),
        ensure_completion_event_fn=ensure_completion_event_fn,
    )


async def retrieve_tasks(
    registry: TaskRegistryLifecycleView,
    database_tasks: DatabaseTasksProtocol,
    task_ids: tuple[str, ...],
    *,
    force_refresh: bool = False,
    ensure_completion_event_fn: Callable[[str, bool], Coroutine[None, None, asyncio.Event]],
) -> list[Task]:
    if not task_ids:
        return []
    if not force_refresh:
        now = time.monotonic()
        cached_tasks: list[Task] = []
        terminal_task_ids: list[str] = []
        async with registry.tasks_lock:
            for task_id in task_ids:
                cached_task = resolve_cached_task_locked(registry, task_id, now=now)
                if cached_task is None:
                    cached_tasks = []
                    break
                cached_tasks.append(cached_task)
                if cached_task.status.is_terminal():
                    terminal_task_ids.append(task_id)
        if cached_tasks:
            for terminal_task_id in terminal_task_ids:
                await ensure_completion_event_fn(terminal_task_id, True)
            return cached_tasks
    rows = await database_tasks.get_unified_tasks_by_ids(task_ids)
    resolved_tasks: list[Task] = []
    resolved_task_ids: set[str] = set()
    for row in rows:
        persisted = task_from_row(registry.task_catalog, row)
        resolved_tasks.append(
            await store_persisted_task(
                registry,
                persisted,
                ensure_completion_event_fn=ensure_completion_event_fn,
            ),
        )
        resolved_task_ids.add(persisted.task_id)
    for task_id in task_ids:
        if task_id not in resolved_task_ids:
            await clear_task_from_caches(registry, task_id)
    return resolved_tasks


async def retrieve_cached_task(registry: TaskRegistryLifecycleView, task_id: str) -> Task | None:
    now = time.monotonic()
    async with registry.tasks_lock:
        return resolve_cached_task_locked(registry, task_id, now=now)
