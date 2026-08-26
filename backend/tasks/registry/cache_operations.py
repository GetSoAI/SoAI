"""SoAI - Task registry cache update and clearing operations [backend/tasks/registry/cache_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from tasks.registry.cache_policy import update_cache_with_incoming_task

if TYPE_CHECKING:
    from asyncio import Event

    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = (
    "clear_task_from_caches",
    "update_task_cache",
)


async def clear_task_from_caches(registry: TaskRegistryLifecycleView, task_id: str) -> None:
    async with registry.tasks_lock:
        registry.tasks.pop(task_id, None)
        registry.terminal_cache.pop(task_id, None)
    await registry.ensure_completion_event(task_id, set_if_terminal=True)


async def update_task_cache(
    registry: TaskRegistryLifecycleView,
    task: Task,
    ensure_completion_event_fn: Callable[[str, bool], Coroutine[None, None, Event]],
) -> None:
    try:
        _ = task.task_id
    except AttributeError as exception:
        raise ValidationError("Task instance is required.") from exception
    await update_cache_with_incoming_task(
        registry,
        task,
        ensure_completion_event_fn=ensure_completion_event_fn,
    )
