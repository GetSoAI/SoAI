"""SoAI - Scheduler pending task registration [backend/orchestrator/queueing/pending_registration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.tasks.enums import TaskStatus
from core.tasks.status_transitions import update_status
from core.tasks.task import Task
from orchestrator.prompt_slot_lifecycle import release_prompt_slot_and_update_cache
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("register_scheduler_pending_task",)


async def register_scheduler_pending_task(
    queue: QueueServiceView,
    task: Task,
    routing_key: str,
    *,
    plugin_name: str | None,
    insert_left: bool,
    refresh_before_transition: bool,
    index_task: bool,
    register_active: bool,
) -> Task:
    if refresh_before_transition:
        refreshed_task = await queue.task_registry.get(task.task_id, force_refresh=True)
        if refreshed_task is not None:
            task = refreshed_task
    if task.status == TaskStatus.DEDUPED:
        return task
    try:
        updated_task = await update_status(
            queue.task_registry,
            task.task_id,
            TaskStatus.AWAITING_SCHEDULER,
        )
    except ValidationError:
        refreshed_task = await queue.task_registry.get(task.task_id, force_refresh=True)
        if refreshed_task and refreshed_task.status == TaskStatus.DEDUPED:
            return refreshed_task
        raise
    if updated_task is None:
        refreshed_task = await queue.task_registry.get(task.task_id, force_refresh=True)
        if refreshed_task is not None:
            task = refreshed_task
        task = await release_prompt_slot_and_update_cache(queue.priority, queue.task_registry, task)
        return task
    task = updated_task
    if index_task and register_active:
        await queue.tracking.register_indexed_active_task(task)
    elif index_task:
        await queue.tracking.index_task(task)
    elif register_active:
        await queue.tracking.register_active_task(task)
    await queue.tracking.register_pending_task(
        task,
        routing_key,
        plugin_name=plugin_name,
        insert_left=insert_left,
    )
    task = await release_prompt_slot_and_update_cache(queue.priority, queue.task_registry, task)
    return task
