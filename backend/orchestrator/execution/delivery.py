"""SoAI - Delivery state management for orchestrator executor [backend/orchestrator/execution/delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.orchestration_context_cache import update_orchestration_context_from_current
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from orchestrator.execution.dependencies import DeliveryManagerDependencies

__all__ = ("DeliveryManager",)


class DeliveryManager:
    def __init__(self, deps: DeliveryManagerDependencies) -> None:
        self._queue: OrchestratorQueueProtocol = deps.queue
        self._task_registry: TaskRegistryProtocol = deps.task_registry

    async def prepare_delivery(self, task: Task) -> tuple[Task, int | None]:
        delivery_version: int | None = None

        def _prepare(context: OrchestrationContext) -> OrchestrationContext:
            nonlocal delivery_version
            if context.delivery_in_progress:
                return context
            delivery_version = context.delivery_version + 1
            return replace(
                context,
                delivery_version=delivery_version,
                delivery_in_progress=True,
            )

        resolved_task = await uncancel_then_cleanup(
            update_orchestration_context_from_current(
                self._task_registry,
                task.task_id,
                _prepare,
            )
        )
        return (resolved_task if resolved_task is not None else task, delivery_version)

    async def clear_delivery_in_progress(self, task: Task, delivery_version: int) -> bool:
        cleared = False

        def _clear(current_context: OrchestrationContext) -> OrchestrationContext:
            nonlocal cleared
            if current_context.delivery_version != delivery_version:
                return current_context
            if not current_context.delivery_in_progress:
                return current_context
            cleared = True
            return replace(current_context, delivery_in_progress=False)

        await update_orchestration_context_from_current(
            self._task_registry,
            task.task_id,
            _clear,
        )
        return cleared
