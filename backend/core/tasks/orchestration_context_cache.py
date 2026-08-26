"""SoAI - Orchestration context cache updates that preserve task lifecycle [backend/core/tasks/orchestration_context_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from core.errors.exceptions import StateError
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task import Task
from core.tasks.task_lock_control import load_task_with_drop_control, task_lock_control

__all__ = (
    "merge_orchestration_context_snapshot",
    "update_orchestration_context_from_current",
)


def _merge_context_snapshot(
    *,
    current: OrchestrationContext,
    incoming: OrchestrationContext,
) -> OrchestrationContext:
    event = incoming.event if incoming.event is not None else current.event
    return replace(
        incoming,
        event=event,
        delivery_in_progress=current.delivery_in_progress or incoming.delivery_in_progress,
        delivery_version=max(current.delivery_version, incoming.delivery_version),
        streaming_started=current.streaming_started or incoming.streaming_started,
        prompt_slot_active=current.prompt_slot_active or incoming.prompt_slot_active,
        prompt_slot_generation=(
            current.prompt_slot_generation
            if current.prompt_slot_active
            else incoming.prompt_slot_generation
        ),
    )


async def update_orchestration_context_from_current(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    transform: Callable[[OrchestrationContext], OrchestrationContext],
) -> Task | None:
    async with task_lock_control(registry, task_id) as lock_control:
        task = await load_task_with_drop_control(registry, lock_control, task_id)
        if task is None or task.status.is_terminal():
            return task
        context = task.orchestration_context
        if context is None:
            raise StateError("Task is missing orchestration_context")
        updated_context = transform(context)
        if updated_context == context:
            return task
        updated_task = task.with_orchestration_context(updated_context)
        await registry.update_task_cache(updated_task)
        return updated_task


async def merge_orchestration_context_snapshot(
    registry: TaskRegistryLifecycleView,
    task: Task,
) -> Task:
    incoming_context = task.orchestration_context
    if incoming_context is None:
        raise StateError("Task is missing orchestration_context")
    async with task_lock_control(registry, task.task_id) as lock_control:
        current_task = await registry.get(task.task_id)
        if current_task is None:
            await registry.update_task_cache(task)
            return task
        if current_task.status.is_terminal():
            lock_control.request_drop_after_exit()
            return current_task
        current_context = current_task.orchestration_context
        updated_context = (
            incoming_context
            if current_context is None
            else _merge_context_snapshot(current=current_context, incoming=incoming_context)
        )
        if updated_context == current_context:
            return current_task
        updated_task = current_task.with_orchestration_context(updated_context)
        await registry.update_task_cache(updated_task)
        return updated_task
