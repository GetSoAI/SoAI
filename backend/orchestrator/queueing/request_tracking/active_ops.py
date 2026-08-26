"""SoAI - Request tracking active/index ops [backend/orchestrator/queueing/request_tracking/active_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from orchestrator.queueing.request_tracking.pending_ops import (
    unlink_pending_token_from_keys,
)
from orchestrator.queueing.request_tracking.state import QueueRequestTrackingState

__all__ = (
    "deindex_task",
    "has_tracking_ref_for_tracking_id",
    "index_task",
    "purge_task_tracking_refs_for_task_id",
    "register_active_task",
    "sync_tracked_task_refs_for_task_id",
    "unregister_active_task",
)


def has_tracking_ref_for_tracking_id(
    state: QueueRequestTrackingState,
    *,
    tracking_id: str,
    task_id: str | None = None,
) -> bool:
    if not tracking_id:
        return False
    active_task = state.active_tasks.get(tracking_id)
    if active_task is not None and (task_id is None or active_task.task_id == task_id):
        return True
    pending_task = state.pending_entries.get(tracking_id)
    if pending_task is not None and (task_id is None or pending_task.task_id == task_id):
        return True
    return False


def sync_tracked_task_refs_for_task_id(
    state: QueueRequestTrackingState,
    *,
    task: Task,
) -> None:
    token_set = state.tracking_ids_by_task_id.get(task.task_id)
    if not token_set:
        return
    for token in list(token_set):
        if token in state.active_tasks:
            state.active_tasks[token] = task
        if token in state.pending_entries:
            state.pending_entries[token] = task


def register_active_task(
    state: QueueRequestTrackingState,
    *,
    require_orchestration_context: Callable[[Task], OrchestrationContext],
    task: Task,
) -> None:
    context = require_orchestration_context(task)
    token = context.tracking_id
    previous = state.active_tasks.get(token)
    if previous is not None and previous.task_id != task.task_id:
        previous_tokens = state.tracking_ids_by_task_id.get(previous.task_id)
        if previous_tokens:
            previous_tokens.discard(token)
            if not previous_tokens:
                state.tracking_ids_by_task_id.pop(previous.task_id, None)
    state.active_tasks[token] = task
    state.tracking_ids_by_task_id[task.task_id].add(token)


def unregister_active_task(
    state: QueueRequestTrackingState,
    *,
    require_orchestration_context: Callable[[Task], OrchestrationContext],
    task: Task,
) -> None:
    token = require_orchestration_context(task).tracking_id
    state.active_tasks.pop(token, None)
    token_set = state.tracking_ids_by_task_id.get(task.task_id)
    if token_set:
        token_set.discard(token)
        if not token_set:
            state.tracking_ids_by_task_id.pop(task.task_id, None)


def index_task(state: QueueRequestTrackingState, *, task: Task) -> None:
    previous = state.tasks_by_id.get(task.task_id)
    if previous is not None and previous.cancellation_id != task.cancellation_id:
        previous_task_ids = state.task_ids_by_cancellation_id.get(previous.cancellation_id)
        if previous_task_ids:
            previous_task_ids.discard(task.task_id)
            if not previous_task_ids:
                state.task_ids_by_cancellation_id.pop(previous.cancellation_id, None)
    state.tasks_by_id[task.task_id] = task
    sync_tracked_task_refs_for_task_id(state, task=task)
    if task.cancellation_id:
        state.task_ids_by_cancellation_id[task.cancellation_id].add(task.task_id)


def deindex_task(state: QueueRequestTrackingState, *, task: Task) -> None:
    state.tasks_by_id.pop(task.task_id, None)
    task_ids = state.task_ids_by_cancellation_id.get(task.cancellation_id)
    if task_ids:
        task_ids.discard(task.task_id)
        if not task_ids:
            state.task_ids_by_cancellation_id.pop(task.cancellation_id, None)


def purge_task_tracking_refs_for_task_id(
    state: QueueRequestTrackingState,
    *,
    task_id: str,
) -> None:
    token_set = state.tracking_ids_by_task_id.pop(task_id, set())
    for token in list(token_set):
        state.active_tasks.pop(token, None)
        unlink_pending_token_from_keys(state, token=token)
