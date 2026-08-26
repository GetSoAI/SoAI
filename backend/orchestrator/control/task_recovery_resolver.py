"""SoAI - Orchestrated task recovery shared resolver [backend/orchestrator/control/task_recovery_resolver.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from orchestrator.control.task_recovery_dependencies import (
    OrchestratedTaskRecoveryDependencies,
)

__all__ = ("OrchestratedTaskRecoveryResolver",)


class OrchestratedTaskRecoveryResolver:
    _RECOVERY_PAGE_SIZE = 500

    def __init__(self, deps: OrchestratedTaskRecoveryDependencies) -> None:
        self._deps = deps

    async def resolve_cancellation_reason(self, task: Task) -> str:
        return (
            await self._deps.cancellation_history.get_reason(task.cancellation_id)
            or "Task was cancelled while orphaned."
        )

    async def resolve_unowned_tracked_task(self, task: Task) -> tuple[Task | None, bool]:
        tracked_task = await self._deps.queue.tracking.get_task_by_id(task.task_id)
        if tracked_task is None:
            return (None, False)
        if await self._deps.queue.tracking.has_task_ownership(tracked_task):
            return (None, True)
        if tracked_task.orchestration_context is None:
            return (None, False)
        resolved_task = tracked_task.with_persisted_state(task)
        await self._deps.task_registry.update_task_cache(resolved_task)
        await self._deps.queue.tracking.update_task(resolved_task)
        return (resolved_task, False)

    async def finalize_without_context(
        self,
        task: Task,
        status: TaskStatus,
        *,
        error_code: int | None = None,
        error_message: str | None = None,
        status_message: str | None = None,
    ) -> None:
        await self._deps.queue.tracking.forget_task(task.task_id)
        await finalize(
            self._deps.task_registry,
            task.task_id,
            status,
            error_code=error_code,
            error_message=error_message,
            status_message=status_message,
        )

    async def query_active_orchestrated_tasks(self) -> list[Task]:
        task_types = tuple(
            task_type
            for task_type in self._deps.task_registry.task_catalog.task_types
            if is_orchestrated_inference_task_type(task_type)
        )
        if not task_types:
            return []
        resolved_by_task_id: dict[str, Task] = {}
        for task_type in task_types:
            after_created_at_ms = 0
            after_task_id = ""
            while True:
                tasks = await self._deps.task_registry_queries.query_active_by_type_keyset(
                    task_type=task_type,
                    after_created_at_ms=after_created_at_ms,
                    after_task_id=after_task_id,
                    limit=self._RECOVERY_PAGE_SIZE,
                )
                if not tasks:
                    break
                for task in tasks:
                    existing = resolved_by_task_id.get(task.task_id)
                    if existing is None or task.updated_at_ms >= existing.updated_at_ms:
                        resolved_by_task_id[task.task_id] = task
                if len(tasks) < self._RECOVERY_PAGE_SIZE:
                    break
                last_task = tasks[-1]
                after_created_at_ms = last_task.created_at_ms
                after_task_id = last_task.task_id
        return list(resolved_by_task_id.values())
