"""SoAI - Priority queue manager composing prompt slots and queue operations [backend/orchestrator/queueing/priority/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import override

from core.orchestrator.protocols_queue import PromptSlotSnapshot
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.task import Task
from orchestrator.queueing.internal_protocols import QueuePriorityProtocol
from orchestrator.queueing.priority.dependencies import QueuePriorityDependencies
from orchestrator.queueing.priority.metrics import ModelMetricsRegistry
from orchestrator.queueing.priority.prompt_slots import PromptSlotState
from orchestrator.queueing.priority.queue_operations import TaskQueueState
from orchestrator.queueing.priority.sentinel import ShutdownSentinel

__all__ = ("QueuePriority",)


class QueuePriority(QueuePriorityProtocol):
    def __init__(self, deps: QueuePriorityDependencies) -> None:
        self._deps = deps
        self.prompt_slot_limit = deps.config.queue_prompt_slot_limit
        self.prompt_slots = PromptSlotState(
            slot_limit=self.prompt_slot_limit,
            enabled=deps.config.prompt_queuing_enabled,
            metrics=deps.metrics,
        )
        self.queue_state = TaskQueueState(
            initial_max_size=deps.config.task_queue_max_size,
            metrics=deps.metrics,
            cycles=deps.cycles,
            shutdown_event=deps.shutdown_event,
            get_total_backlog_size=deps.get_total_backlog_size,
            require_orchestration_context=deps.require_orchestration_context,
            model_metrics_registry=ModelMetricsRegistry(),
        )

    @property
    @override
    def prompt_queuing_enabled(self) -> bool:
        return bool(self.prompt_slots.enabled)

    @property
    @override
    def task_queue(self) -> asyncio.Queue[Task | type[ShutdownSentinel]]:
        return self.queue_state.queue_resource.current

    @override
    async def drain_task_queue(self) -> list[Task]:
        return await self.queue_state.drain()

    def apply_runtime_config(self, config: OrchestratorRuntimeConfig) -> None:
        self.queue_state.apply_runtime_config(config.task_queue_max_size)
        self.prompt_slot_limit = config.queue_prompt_slot_limit
        self.prompt_slots.update_mode(
            config.prompt_queuing_enabled,
            slot_limit=self.prompt_slot_limit,
        )

    @override
    def signal_shutdown(self, worker_count: int) -> None:
        normalized_worker_count = max(0, worker_count)
        self.queue_state.signal_shutdown(normalized_worker_count)

    @override
    async def acquire_prompt_slot(self, task: Task) -> Task:
        return await self.prompt_slots.acquire(
            task,
            self._deps.require_orchestration_context,
        )

    @override
    def release_prompt_slot(self, task: Task) -> Task:
        return self.prompt_slots.release(
            task,
            self._deps.require_orchestration_context,
        )

    @override
    def get_prompt_slot_snapshot(self) -> PromptSlotSnapshot:
        return self.prompt_slots.snapshot()

    @override
    async def enqueue_task(self, task: Task) -> None:
        queued_task = task
        await self.queue_state.enqueue(queued_task)

    @override
    async def take_task(self) -> Task | None:
        return await self.queue_state.take()
