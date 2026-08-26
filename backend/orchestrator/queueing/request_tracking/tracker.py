"""SoAI - Request tracking for pending and active orchestrator tasks [backend/orchestrator/queueing/request_tracking/tracker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import deque

from core.orchestrator.request_priority import RequestPriority
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from orchestrator.queueing.request_tracking.active_ops import (
    deindex_task,
    has_tracking_ref_for_tracking_id,
    index_task,
    purge_task_tracking_refs_for_task_id,
    register_active_task,
    unregister_active_task,
)
from orchestrator.queueing.request_tracking.dependencies import (
    QueueRequestTrackingDependencies,
)
from orchestrator.queueing.request_tracking.pending_ops import (
    register_pending_task,
    unregister_pending_queue_locked,
    unregister_pending_task_by_token_locked,
    unregister_pending_task_token_for_key,
)
from orchestrator.queueing.request_tracking.queries import (
    count_prompt_slot_active_tasks,
    get_pending_priority_counts,
    get_pending_universal_ids_for_plugins,
    get_pending_universal_ids_snapshot,
    get_tasks_by_ids,
    get_tasks_by_status,
    get_tasks_for_cancellation_id,
    peek_pending_task,
    snapshot_pending_summary,
)
from orchestrator.queueing.request_tracking.state import create_tracking_state

__all__ = ("QueueRequestTracking",)


class QueueRequestTracking:
    def __init__(self, deps: QueueRequestTrackingDependencies) -> None:
        self._deps = deps
        self._state = create_tracking_state()
        self.pending_by_routing_key = self._state.pending_by_routing_key
        self.last_deferral_reason = self._state.last_deferral_reason

    async def count_prompt_slot_active_tasks(self) -> int:
        async with self._state.tasks_lock:
            return count_prompt_slot_active_tasks(self._state)

    async def index_task(self, task: Task) -> None:
        async with self._state.tasks_lock:
            index_task(self._state, task=task)

    async def update_task(self, task: Task) -> None:
        async with self._state.tasks_lock:
            index_task(self._state, task=task)

    async def get_task_by_id(self, task_id: str) -> Task | None:
        if not task_id:
            return None
        async with self._state.tasks_lock:
            return self._state.tasks_by_id.get(task_id)

    async def forget_task(self, task_id: str) -> None:
        if not task_id:
            return
        async with self._state.tasks_lock:
            task = self._state.tasks_by_id.get(task_id)
            purge_task_tracking_refs_for_task_id(self._state, task_id=task_id)
            if task is not None:
                deindex_task(self._state, task=task)
                return
            for cancellation_id, task_ids in list(self._state.task_ids_by_cancellation_id.items()):
                task_ids.discard(task_id)
                if not task_ids:
                    self._state.task_ids_by_cancellation_id.pop(cancellation_id, None)

    async def has_task_ownership(self, task: Task) -> bool:
        context = task.orchestration_context
        if context is None:
            return False
        async with self._state.tasks_lock:
            return has_tracking_ref_for_tracking_id(
                self._state,
                tracking_id=context.tracking_id,
                task_id=task.task_id,
            )

    async def get_tasks_for_cancellation_id(self, cancellation_id: str) -> list[Task]:
        if not cancellation_id:
            return []
        async with self._state.tasks_lock:
            return get_tasks_for_cancellation_id(self._state, cancellation_id)

    async def get_cancellation_ids_snapshot(self) -> set[str]:
        async with self._state.tasks_lock:
            return set(self._state.task_ids_by_cancellation_id.keys())

    async def get_pending_keys(self) -> set[str]:
        async with self._state.tasks_lock:
            return set(self._state.pending_by_routing_key.keys())

    async def has_pending_tasks(self) -> bool:
        async with self._state.tasks_lock:
            return any(self._state.pending_by_routing_key.values())

    async def get_pending_universal_ids_snapshot(self) -> dict[str, set[str]]:
        async with self._state.tasks_lock:
            return get_pending_universal_ids_snapshot(self._state)

    async def get_pending_universal_ids_for_plugins(self, plugin_names: set[str]) -> set[str]:
        async with self._state.tasks_lock:
            return get_pending_universal_ids_for_plugins(self._state, plugin_names)

    async def add_pending_universal_id_for_plugin(
        self,
        plugin_name: str,
        universal_id: str,
    ) -> None:
        if not plugin_name or not universal_id:
            return
        async with self._state.tasks_lock:
            self._state.pending_universal_ids_by_plugin[plugin_name].add(universal_id)

    async def peek_pending_task(
        self,
        key: str,
    ) -> tuple[Task | None, str | None, TaskStatus | None]:
        async with self._state.tasks_lock:
            return peek_pending_task(self._state, key)

    async def move_pending_task(
        self,
        task: Task,
        from_key: str,
        to_key: str,
        *,
        insert_left: bool = False,
    ) -> bool:
        token = self._deps.require_orchestration_context(task).tracking_id
        async with self._state.tasks_lock:
            queue = self._state.pending_by_routing_key.get(from_key)
            if queue and (queue[0] == token):
                unregister_pending_task_token_for_key(
                    self._state,
                    require_orchestration_context=self._deps.require_orchestration_context,
                    task=task,
                    key=from_key,
                )
                register_pending_task(
                    self._state,
                    require_orchestration_context=self._deps.require_orchestration_context,
                    key=to_key,
                    task=task,
                    insert_left=insert_left,
                )
                return True
            if to_key in self._state.pending_keys.get(token, set()):
                return True
        return False

    async def unregister_pending_queue(self, key: str) -> deque[Task]:
        async with self._state.tasks_lock:
            return unregister_pending_queue_locked(self._state, key=key)

    async def unregister_pending_task_token_for_key(self, task: Task, key: str) -> None:
        async with self._state.tasks_lock:
            unregister_pending_task_token_for_key(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                task=task,
                key=key,
            )

    async def register_active_task(self, task: Task) -> None:
        async with self._state.tasks_lock:
            register_active_task(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                task=task,
            )

    async def register_indexed_active_task(self, task: Task) -> None:
        async with self._state.tasks_lock:
            index_task(self._state, task=task)
            register_active_task(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                task=task,
            )

    async def unregister_active_task(self, task: Task) -> None:
        async with self._state.tasks_lock:
            unregister_active_task(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                task=task,
            )

    async def cleanup_completed_task(self, task: Task) -> None:
        async with self._state.tasks_lock:
            unregister_active_task(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                task=task,
            )
            unregister_pending_task_by_token_locked(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                task=task,
            )
            deindex_task(self._state, task=task)

    async def register_pending_task(
        self,
        task: Task,
        routing_key: str,
        *,
        plugin_name: str | None,
        insert_left: bool,
    ) -> None:
        async with self._state.tasks_lock:
            register_pending_task(
                self._state,
                require_orchestration_context=self._deps.require_orchestration_context,
                key=routing_key,
                task=task,
                insert_left=insert_left,
            )
            if plugin_name:
                self._state.pending_universal_ids_by_plugin[plugin_name].add(routing_key)

    async def set_deferral_reason(self, key: str | None, reason: str) -> None:
        if key is None:
            return
        async with self._state.tasks_lock:
            self._state.last_deferral_reason[key] = reason

    async def snapshot_pending_summary(self) -> dict[str, int]:
        async with self._state.tasks_lock:
            return snapshot_pending_summary(self._state)

    async def get_pending_priority_counts(self) -> dict[RequestPriority, int]:
        async with self._state.tasks_lock:
            return get_pending_priority_counts(self._state)

    async def get_total_pending_count(self) -> int:
        async with self._state.tasks_lock:
            return self._state.pending_total_count

    async def get_tasks_by_ids(self, task_ids: set[str]) -> list[Task]:
        async with self._state.tasks_lock:
            return get_tasks_by_ids(self._state, task_ids)

    async def get_tasks_by_status(self, status: TaskStatus) -> list[Task]:
        async with self._state.tasks_lock:
            return get_tasks_by_status(self._state, status)
