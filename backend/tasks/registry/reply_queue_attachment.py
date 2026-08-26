"""SoAI - Task registry reply queue attachment operations [backend/tasks/registry/reply_queue_attachment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    import asyncio

    from core.events.types_base import Event
    from core.tasks.protocols import TaskLockView, TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = ("attach_reply_queue_to_task",)


async def attach_reply_queue_to_task(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    reply_queue: asyncio.Queue[Event],
    *,
    get_task_fn: Callable[[str], Awaitable[Task | None]],
    get_task_lock_fn: Callable[[str], TaskLockView],
    bind_identity_fn: Callable[[asyncio.Queue[Event], str, int], None],
) -> Task | None:
    normalized_task_id = (task_id or "").strip()
    if not normalized_task_id:
        raise ValidationError("task_id must be a non-empty string.")
    if reply_queue is None:
        raise ValidationError("reply_queue is required.")
    lock_wrapper = get_task_lock_fn(normalized_task_id)
    async with lock_wrapper.lock:
        task = await get_task_fn(normalized_task_id)
        if task is None:
            return None
        if task.status.is_terminal():
            return task
        if task.reply_queue is not None:
            bind_identity_fn(task.reply_queue, task.task_id, task.user_id)
            return task
        task = task.with_reply_queue(reply_queue)
        bind_identity_fn(reply_queue, task.task_id, task.user_id)
        async with registry.tasks_lock:
            registry.tasks[task.task_id] = task
        return task
