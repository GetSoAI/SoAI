"""SoAI - Task cancellation requests and notifications [backend/core/tasks/task_cancellation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses

from core.runtime.protocols import RequestContextProtocol
from core.tasks.cancellation import publish_cancel
from core.tasks.cancellation_ids import require_cancellation_id
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task import Task
from core.tasks.task_lock_control import load_task_with_drop_control, task_lock_control
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.timing.epoch import epoch_ms

__all__ = (
    "cancel",
    "mark_task_cancellation_requested",
    "request_cancellation_scope",
    "request_task_cancellation",
)


async def request_cancellation_scope(
    registry: TaskRegistryLifecycleView,
    cancellation_id: str,
    reason: str = "Cancelled by user",
) -> None:
    normalized_id = require_cancellation_id(cancellation_id)
    normalized_reason = str(reason or "").strip() or "Cancelled by user"
    cancellation_timestamp = epoch_ms()
    await registry.database_tasks.update_cancellation_requested_at_ms_for_cancellation_id(
        normalized_id,
        cancellation_timestamp,
    )
    await registry.cancellation_coordinator.cancel_scope(normalized_id, normalized_reason)


async def request_task_cancellation(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    reason: str = "Cancelled by user",
) -> Task | None:
    normalized_reason = str(reason or "").strip() or "Cancelled by user"
    result_task = await mark_task_cancellation_requested(registry, task_id)
    if result_task is None:
        return None
    await registry.cancellation_coordinator.cancel_scope(
        result_task.cancellation_id,
        normalized_reason,
    )
    return result_task


async def mark_task_cancellation_requested(
    registry: TaskRegistryLifecycleView,
    task_id: str,
) -> Task | None:
    async with task_lock_control(registry, task_id) as lock_control:
        task = await load_task_with_drop_control(registry, lock_control, task_id)
        if task is None:
            return None
        if task.status.is_terminal():
            return task
        if task.cancellation_requested_at_ms is None:
            cancellation_timestamp = epoch_ms()
            task = dataclasses.replace(
                task,
                cancellation_requested_at_ms=cancellation_timestamp,
                update_counter=task.update_counter + 1,
            )
            await registry.database_tasks.update_cancellation_requested_at_ms(
                task_id,
                cancellation_timestamp,
            )
            await registry.update_task_cache(task)
        return task


async def cancel(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    reason: str = "Cancelled by user",
    *,
    context: RequestContextProtocol | None = None,
    mutation_fencing_token: int | None = None,
) -> Task | None:
    cancellation_id: str | None = None
    normalized_reason = str(reason or "").strip() or "Cancelled by user"
    is_orchestrated = False
    requires_fenced_finalization = False
    result_task: Task | None = None

    async with task_lock_control(registry, task_id) as lock_control:
        task = await load_task_with_drop_control(registry, lock_control, task_id)
        if task is None:
            return None
        if task.status.is_terminal():
            return task
        if task.cancellation_requested_at_ms is None:
            cancellation_timestamp = epoch_ms()
            task = dataclasses.replace(
                task,
                cancellation_requested_at_ms=cancellation_timestamp,
                update_counter=task.update_counter + 1,
            )
            await registry.database_tasks.update_cancellation_requested_at_ms(
                task_id,
                cancellation_timestamp,
            )
            await registry.update_task_cache(task)
        cancellation_id = task.cancellation_id
        is_orchestrated = is_orchestrated_inference_task_type(task.task_type)
        result_task = task

    requires_fenced_finalization = (
        await registry.database_tasks.mutation_requires_fenced_finalization(task_id)
    )
    if not requires_fenced_finalization:
        await publish_cancel(
            registry.event_bus,
            registry.cancellation_coordinator,
            registry.cancellation_history,
            context,
            normalized_reason,
            cancellation_id=cancellation_id,
        )
    if is_orchestrated or (requires_fenced_finalization and mutation_fencing_token is None):
        return result_task
    return await finalize(
        registry,
        task_id,
        TaskStatus.CANCELLED,
        error_message=normalized_reason,
        status_message=normalized_reason,
        mutation_fencing_token=mutation_fencing_token,
    )
