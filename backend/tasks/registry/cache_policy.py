"""SoAI - Task registry cache policy helpers [backend/tasks/registry/cache_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING

from core.tasks.eviction import cleanup_evicted_events, evict_if_needed
from core.tasks.task_registry_cache import resolve_cached_task_locked
from core.tasks.task_state_merge import merge_task_state

if TYPE_CHECKING:
    import asyncio

    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = (
    "prune_terminal_cache_entries",
    "resolve_cached_task_locked",
    "store_persisted_task",
    "update_cache_with_incoming_task",
)


async def update_cache_with_incoming_task(
    registry: TaskRegistryLifecycleView,
    incoming: Task,
    *,
    ensure_completion_event_fn: Callable[[str, bool], Coroutine[None, None, asyncio.Event]],
) -> Task:
    now = time.monotonic()
    task_id = incoming.task_id
    evicted_ids: list[str] = []
    resolved: Task
    should_return_early = False
    async with registry.tasks_lock:
        cached = resolve_cached_task_locked(registry, task_id, now=now)
        resolved = merge_task_state(cached=cached, incoming=incoming)
        if cached is not None and resolved is cached:
            should_return_early = True
        if not should_return_early:
            if resolved.status.is_terminal():
                resolved_task_without_queue, _ = resolved.without_reply_queue()
                registry.tasks.pop(task_id, None)
                registry.terminal_cache[task_id] = (resolved_task_without_queue, now)
                resolved = resolved_task_without_queue
            else:
                registry.terminal_cache.pop(task_id, None)
                registry.tasks[task_id] = resolved
                evicted_ids = evict_if_needed(registry)
    if should_return_early:
        if resolved.status.is_terminal():
            await ensure_completion_event_fn(task_id, True)
        return resolved
    if evicted_ids:
        await cleanup_evicted_events(registry, evicted_ids)
    if resolved.status.is_terminal():
        await ensure_completion_event_fn(task_id, True)
    return resolved


async def store_persisted_task(
    registry: TaskRegistryLifecycleView,
    persisted: Task,
    *,
    ensure_completion_event_fn: Callable[[str, bool], Coroutine[None, None, asyncio.Event]],
) -> Task:
    return await update_cache_with_incoming_task(
        registry,
        persisted,
        ensure_completion_event_fn=ensure_completion_event_fn,
    )


def prune_terminal_cache_entries(
    registry: TaskRegistryLifecycleView,
    *,
    now: float,
    batch_size: int,
) -> list[str]:
    if not registry.terminal_cache:
        return []
    removed_ids: list[str] = []
    candidate_task_ids = tuple(registry.terminal_cache.keys())
    for task_id in candidate_task_ids[: batch_size * 2]:
        entry = registry.terminal_cache.get(task_id)
        if entry is None:
            continue
        _task, cached_at = entry
        if now - cached_at >= registry.terminal_cache_ttl:
            del registry.terminal_cache[task_id]
            removed_ids.append(task_id)
            if len(removed_ids) >= batch_size:
                break
    return removed_ids
