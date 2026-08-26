"""SoAI - Queue-cycle state transitions [backend/orchestrator/queueing/cycle_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.concurrency.protocols import TaskDoneQueueProtocol
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_orchestrator import (
    ORCHESTRATOR_COUNTER_INVARIANT_VIOLATION,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.protocols_queue import QueueCycleType
from orchestrator.queueing.cycle_errors import (
    queue_cycle_already_open_error_type,
    queue_cycle_open_operation,
)

__all__ = ("QueueCycleStateStore",)

LOGGER_NAME_ORCHESTRATOR_QUEUE = "SoAI.orchestrator.queueing.queue"


@dataclass(slots=True)
class TaskQueueCycleState:
    priority_queue: TaskDoneQueueProtocol | None = None
    plugin_queue: TaskDoneQueueProtocol | None = None

    def get_queue(self, cycle_type: QueueCycleType) -> TaskDoneQueueProtocol | None:
        if cycle_type is QueueCycleType.PRIORITY:
            return self.priority_queue
        return self.plugin_queue

    def set_queue(self, cycle_type: QueueCycleType, queue: TaskDoneQueueProtocol | None) -> None:
        if cycle_type is QueueCycleType.PRIORITY:
            self.priority_queue = queue
            return
        self.plugin_queue = queue

    def is_empty(self) -> bool:
        return self.priority_queue is None and self.plugin_queue is None


class QueueCycleStateStore:
    def __init__(self, metrics: MetricsManagerProtocol | None) -> None:
        self._metrics = metrics
        self._task_locks = TTLAsyncLockRegistry[str](TTLAsyncLockRegistryDependencies())
        self._task_states: dict[str, TaskQueueCycleState] = {}
        self._open_priority_cycles = 0
        self._open_plugin_cycles = 0

    def get_open_counts(self) -> dict[str, int]:
        return {
            QueueCycleType.PRIORITY.value: self._open_priority_cycles,
            QueueCycleType.PLUGIN.value: self._open_plugin_cycles,
        }

    def _decrement_open_count(self, cycle_type: QueueCycleType, *, operation: str) -> None:
        logger = get_logger(LOGGER_NAME_ORCHESTRATOR_QUEUE)
        if cycle_type is QueueCycleType.PRIORITY:
            self._open_priority_cycles -= 1
            if self._open_priority_cycles < 0:
                self._open_priority_cycles = 0
                if self._metrics is not None:
                    self._metrics.increment_counter(*ORCHESTRATOR_COUNTER_INVARIANT_VIOLATION)
                logger.warning(
                    "Invariant violation: open priority cycle counter underflow (operation=%s).",
                    operation,
                )
            return
        self._open_plugin_cycles -= 1
        if self._open_plugin_cycles < 0:
            self._open_plugin_cycles = 0
            if self._metrics is not None:
                self._metrics.increment_counter(*ORCHESTRATOR_COUNTER_INVARIANT_VIOLATION)
            logger.warning(
                "Invariant violation: open plugin cycle counter underflow (operation=%s).",
                operation,
            )

    def _increment_open_count(self, cycle_type: QueueCycleType) -> None:
        if cycle_type is QueueCycleType.PRIORITY:
            self._open_priority_cycles += 1
            return
        self._open_plugin_cycles += 1

    def _raise_cycle_already_open(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        existing_queue: TaskDoneQueueProtocol,
        source_queue: TaskDoneQueueProtocol,
    ) -> None:
        error_type = queue_cycle_already_open_error_type(cycle_type)
        raise error_type(
            f"Queue cycle already open for task '{task_id}' and type '{cycle_type.value}'.",
            operation=queue_cycle_open_operation(cycle_type),
            details={
                "task_id": task_id,
                "cycle_type": cycle_type.value,
                "existing_queue_id": id(existing_queue),
                "source_queue_id": id(source_queue),
            },
        )

    async def open_cycle_and_enqueue_nowait(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        queue: TaskDoneQueueProtocol,
        enqueue: Callable[[], None],
    ) -> None:
        async with self._task_locks[task_id]:
            state = self._task_states.get(task_id)
            if state is None:
                state = TaskQueueCycleState()
            existing_queue = state.get_queue(cycle_type)
            if existing_queue is not None:
                self._raise_cycle_already_open(task_id, cycle_type, existing_queue, queue)
            enqueue()
            self._task_states[task_id] = state
            state.set_queue(cycle_type, queue)
            self._increment_open_count(cycle_type)

    async def abandon_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
    ) -> bool:
        return await self._clear_cycle(
            task_id,
            cycle_type,
            operation=f"orchestrator.queue_cycles.abandon_{cycle_type.value}",
        )

    async def migrate_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        target_queue: TaskDoneQueueProtocol,
    ) -> TaskDoneQueueProtocol | None:
        async with self._task_locks[task_id]:
            state = self._task_states.get(task_id)
            if state is None:
                return None
            source_queue = state.get_queue(cycle_type)
            if source_queue is None:
                return None
            state.set_queue(cycle_type, target_queue)
            return source_queue

    async def close_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
    ) -> TaskDoneQueueProtocol | None:
        async with self._task_locks[task_id]:
            state = self._task_states.get(task_id)
            if state is None:
                return None
            queue = state.get_queue(cycle_type)
            if queue is None:
                return None
            state.set_queue(cycle_type, None)
            if state.is_empty():
                self._task_states.pop(task_id, None)
            self._decrement_open_count(
                cycle_type,
                operation=f"orchestrator.queue_cycles.close_{cycle_type.value}",
            )
            return queue

    async def _clear_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        *,
        operation: str,
    ) -> bool:
        async with self._task_locks[task_id]:
            state = self._task_states.get(task_id)
            if state is None:
                return False
            queue = state.get_queue(cycle_type)
            if queue is None:
                return False
            state.set_queue(cycle_type, None)
            if state.is_empty():
                self._task_states.pop(task_id, None)
            self._decrement_open_count(cycle_type, operation=operation)
            return True
