"""SoAI - Durable orchestrated cancellation target loading [backend/orchestrator/control/cancellation_targets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.protocols_query import TaskRegistryQueryView
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from core.validation.integers import is_strict_int
from orchestrator.queueing.internal_protocols import QueueRequestTrackingProtocol

__all__ = ("load_orchestrated_cancel_targets",)

_CANCELLATION_PAGE_SIZE = 1000


async def _query_orchestrated_cancellation_tasks(
    *,
    cancellation_id: str,
    task_registry_queries: TaskRegistryQueryView,
) -> list[Task]:
    after_created_at_ms = 0
    after_task_id = ""
    resolved_tasks: list[Task] = []
    while True:
        tasks = await task_registry_queries.query_active_for_cancellation_id_keyset(
            cancellation_id,
            after_created_at_ms=after_created_at_ms,
            after_task_id=after_task_id,
            limit=_CANCELLATION_PAGE_SIZE,
        )
        if not tasks:
            return resolved_tasks
        for task in tasks:
            if is_orchestrated_inference_task_type(task.task_type):
                resolved_tasks.append(task)
        if len(tasks) < _CANCELLATION_PAGE_SIZE:
            return resolved_tasks
        last_task = tasks[-1]
        last_task_id = last_task.task_id
        last_created_at_ms = last_task.created_at_ms
        if not isinstance(last_task_id, str) or not last_task_id:
            raise ValidationError("Cancellation query returned a task without task_id.")
        if not is_strict_int(last_created_at_ms):
            raise ValidationError("Cancellation query returned a task with invalid created_at_ms.")
        after_task_id = last_task_id
        after_created_at_ms = last_created_at_ms


async def load_orchestrated_cancel_targets(
    *,
    cancellation_id: str,
    tracking: QueueRequestTrackingProtocol,
    task_registry: TaskRegistryProtocol,
    task_registry_queries: TaskRegistryQueryView,
) -> list[Task]:
    tracked_tasks = await tracking.get_tasks_for_cancellation_id(cancellation_id)
    tracked_by_id = {
        task.task_id: task
        for task in tracked_tasks
        if is_orchestrated_inference_task_type(task.task_type)
    }
    query_tasks = await _query_orchestrated_cancellation_tasks(
        cancellation_id=cancellation_id,
        task_registry_queries=task_registry_queries,
    )
    resolved_targets: list[Task] = []
    seen_task_ids: set[str] = set()
    for persisted_task in query_tasks:
        if persisted_task.status.is_terminal():
            continue
        tracked_task = tracked_by_id.pop(persisted_task.task_id, None)
        resolved_task = (
            persisted_task
            if tracked_task is None
            else tracked_task.with_persisted_state(persisted_task)
        )
        await task_registry.update_task_cache(resolved_task)
        if resolved_task.orchestration_context is not None:
            await tracking.update_task(resolved_task)
        resolved_targets.append(resolved_task)
        seen_task_ids.add(resolved_task.task_id)
    for tracked_task in tracked_by_id.values():
        if tracked_task.task_id in seen_task_ids:
            continue
        if tracked_task.status.is_terminal():
            continue
        await task_registry.update_task_cache(tracked_task)
        if tracked_task.orchestration_context is not None:
            await tracking.update_task(tracked_task)
        resolved_targets.append(tracked_task)
    return resolved_targets
