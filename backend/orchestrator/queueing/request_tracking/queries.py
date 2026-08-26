"""SoAI - Queue request tracking state queries [backend/orchestrator/queueing/request_tracking/queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque

from core.orchestrator.request_priority import RequestPriority
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from orchestrator.queueing.request_tracking.active_ops import (
    sync_tracked_task_refs_for_task_id,
)
from orchestrator.queueing.request_tracking.state import QueueRequestTrackingState

__all__ = (
    "count_prompt_slot_active_tasks",
    "get_pending_universal_ids_for_plugins",
    "get_pending_universal_ids_snapshot",
    "get_pending_priority_counts",
    "get_tasks_by_ids",
    "get_tasks_by_status",
    "get_tasks_for_cancellation_id",
    "peek_pending_task",
    "snapshot_pending_summary",
)


def count_prompt_slot_active_tasks(state: QueueRequestTrackingState) -> int:
    count = 0
    for task in state.tasks_by_id.values():
        context = task.orchestration_context
        if context is not None and context.prompt_slot_active:
            count += 1
    return count


def get_tasks_for_cancellation_id(
    state: QueueRequestTrackingState,
    cancellation_id: str,
) -> list[Task]:
    task_ids = set(state.task_ids_by_cancellation_id.get(cancellation_id, set()))
    tasks: list[Task] = []
    for task_id in task_ids:
        task = state.tasks_by_id.get(task_id)
        if task is not None:
            sync_tracked_task_refs_for_task_id(state, task=task)
            tasks.append(task)
    return tasks


def get_pending_universal_ids_snapshot(
    state: QueueRequestTrackingState,
) -> dict[str, set[str]]:
    return {
        name: set(universal_ids)
        for name, universal_ids in state.pending_universal_ids_by_plugin.items()
        if universal_ids
    }


def get_pending_priority_counts(
    state: QueueRequestTrackingState,
) -> dict[RequestPriority, int]:
    counts = {priority: 0 for priority in RequestPriority}
    for task in state.pending_entries.values():
        priority = task.require_orchestration_context().priority_assignment.priority
        counts[priority] += 1
    return counts


def get_pending_universal_ids_for_plugins(
    state: QueueRequestTrackingState,
    plugin_names: set[str],
) -> set[str]:
    return {
        universal_id
        for name in plugin_names
        for universal_id in state.pending_universal_ids_by_plugin.get(name, set())
    }


def peek_pending_task(
    state: QueueRequestTrackingState,
    key: str,
) -> tuple[Task | None, str | None, TaskStatus | None]:
    queue: deque[str] | None = state.pending_by_routing_key.get(key)
    if not queue:
        return (None, None, None)
    token = queue[0]
    task = state.active_tasks.get(token) or state.pending_entries.get(token)
    if task is not None:
        authoritative_task = state.tasks_by_id.get(task.task_id)
        if authoritative_task is not None:
            task = authoritative_task
            sync_tracked_task_refs_for_task_id(state, task=task)
    return (task, token, task.status if task else None)


def snapshot_pending_summary(state: QueueRequestTrackingState) -> dict[str, int]:
    return {
        routing_key: len(requests) for routing_key, requests in state.pending_by_routing_key.items()
    }


def get_tasks_by_ids(state: QueueRequestTrackingState, task_ids: set[str]) -> list[Task]:
    return [state.tasks_by_id[task_id] for task_id in task_ids if task_id in state.tasks_by_id]


def get_tasks_by_status(state: QueueRequestTrackingState, status: TaskStatus) -> list[Task]:
    return [task for task in state.tasks_by_id.values() if task.status == status]
