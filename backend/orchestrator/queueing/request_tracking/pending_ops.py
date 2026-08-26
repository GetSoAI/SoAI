"""SoAI - Request tracking pending ops [backend/orchestrator/queueing/request_tracking/pending_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable

from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from orchestrator.queueing.request_scheduling import request_scheduling_key
from orchestrator.queueing.request_tracking.state import QueueRequestTrackingState

__all__ = (
    "cleanup_final_pending_token_refs_locked",
    "discard_pending_token_from_key",
    "register_pending_task",
    "remove_pending_universal_id_from_plugins",
    "unlink_pending_token_from_keys",
    "unregister_pending_queue_locked",
    "unregister_pending_task_by_token_locked",
    "unregister_pending_task_token_for_key",
)


def _normalize_pending_key(value: str | bytes) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def register_pending_task(
    state: QueueRequestTrackingState,
    *,
    require_orchestration_context: Callable[[Task], OrchestrationContext],
    key: str,
    task: Task,
    insert_left: bool,
) -> None:
    context = require_orchestration_context(task)
    token = context.tracking_id
    existing_pending = state.pending_entries.get(token)
    if existing_pending is not None and existing_pending.task_id != task.task_id:
        unlink_pending_token_from_keys(state, token=token)
    existing_keys = state.pending_keys.get(token)
    if existing_keys:
        for existing_key in list(existing_keys):
            if existing_key != key:
                discard_pending_token_from_key(state, key=existing_key, token=token)
                existing_keys.discard(existing_key)
    queue = state.pending_by_routing_key[key]
    token_added = False
    if token in queue:
        queue.remove(token)
    else:
        token_added = True
    scheduling_key = request_scheduling_key(task)
    scheduling_order = (scheduling_key.priority_order, scheduling_key.queued_at)
    insertion_index = len(queue)
    for index, queued_token in enumerate(queue):
        queued_task = state.pending_entries.get(queued_token)
        if queued_task is None:
            continue
        queued_key = request_scheduling_key(queued_task)
        queued_order = (queued_key.priority_order, queued_key.queued_at)
        if scheduling_order < queued_order or (insert_left and scheduling_order == queued_order):
            insertion_index = index
            break
    queue.insert(insertion_index, token)
    if token_added:
        state.pending_total_count += 1
    state.pending_keys[token].add(key)
    state.pending_entries[token] = task


def remove_pending_universal_id_from_plugins(
    state: QueueRequestTrackingState,
    *universal_ids: str | None,
    plugin_name: str | None = None,
) -> None:
    targets = {universal_id for universal_id in universal_ids if universal_id is not None}
    if not targets:
        return
    if plugin_name:
        plugin_universal_ids = state.pending_universal_ids_by_plugin.get(plugin_name)
        if not plugin_universal_ids:
            return
        plugin_universal_ids.difference_update(targets)
        if not plugin_universal_ids:
            state.pending_universal_ids_by_plugin.pop(plugin_name, None)
        return
    for name in list(state.pending_universal_ids_by_plugin):
        plugin_universal_ids = state.pending_universal_ids_by_plugin.get(name)
        if not plugin_universal_ids:
            continue
        plugin_universal_ids.difference_update(targets)
        if not plugin_universal_ids:
            state.pending_universal_ids_by_plugin.pop(name, None)


def discard_pending_token_from_key(
    state: QueueRequestTrackingState,
    *,
    key: str,
    token: str,
) -> bool:
    queue = state.pending_by_routing_key.get(key)
    if not queue:
        return False
    try:
        queue.remove(token)
    except ValueError:
        return False
    state.pending_total_count = max(0, state.pending_total_count - 1)
    if queue:
        return True
    state.pending_by_routing_key.pop(key, None)
    state.last_deferral_reason.pop(key, None)
    remove_pending_universal_id_from_plugins(state, key)
    return True


def cleanup_final_pending_token_refs_locked(
    state: QueueRequestTrackingState,
    *,
    token: str,
    task_id: str | None = None,
) -> None:
    if task_id is None:
        task = state.pending_entries.get(token)
        task_id = task.task_id if task else None
    state.pending_keys.pop(token, None)
    state.pending_entries.pop(token, None)


def unlink_pending_token_from_keys(
    state: QueueRequestTrackingState,
    *,
    token: str,
    keys: str | bytes | Iterable[str | bytes] | None = None,
) -> None:
    key_set = state.pending_keys.get(token)
    if isinstance(keys, str | bytes):
        keys = [_normalize_pending_key(keys)]
    if keys is None:
        if not key_set:
            return
        targets = list(key_set)
    else:
        base_keys = [_normalize_pending_key(key) for key in keys]
        targets = base_keys if not key_set else [key for key in base_keys if key in key_set]
        if not targets:
            return
    for pending_key in targets:
        discard_pending_token_from_key(state, key=pending_key, token=token)
        if key_set:
            key_set.discard(pending_key)
    if not key_set:
        cleanup_final_pending_token_refs_locked(state, token=token)


def unregister_pending_task_by_token_locked(
    state: QueueRequestTrackingState,
    *,
    require_orchestration_context: Callable[[Task], OrchestrationContext],
    task: Task,
) -> None:
    token = require_orchestration_context(task).tracking_id
    unlink_pending_token_from_keys(state, token=token)


def unregister_pending_task_token_for_key(
    state: QueueRequestTrackingState,
    *,
    require_orchestration_context: Callable[[Task], OrchestrationContext],
    task: Task,
    key: str,
) -> None:
    token = require_orchestration_context(task).tracking_id
    unlink_pending_token_from_keys(state, token=token, keys=key)


def unregister_pending_queue_locked(
    state: QueueRequestTrackingState,
    *,
    key: str,
) -> deque[Task]:
    queue = state.pending_by_routing_key.pop(key, None)
    if not queue:
        state.last_deferral_reason.pop(key, None)
        remove_pending_universal_id_from_plugins(state, key)
        return deque()
    state.pending_total_count = max(0, state.pending_total_count - len(queue))
    tasks: deque[Task] = deque()
    for token in list(queue):
        task = state.pending_entries.get(token)
        if not task:
            continue
        tasks.append(task)
        unlink_pending_token_from_keys(state, token=token, keys=key)
    state.last_deferral_reason.pop(key, None)
    remove_pending_universal_id_from_plugins(state, key)
    return tasks
