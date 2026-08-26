"""SoAI - Runtime queue-cycle ownership for orchestrator task queues [backend/orchestrator/queueing/cycles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.protocols import TaskDoneQueueProtocol
from core.di.validation import require_dependencies
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_orchestrator import (
    ORCHESTRATOR_COUNTER_QUEUE_DOUBLE_FINALIZATION,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.protocols_queue import QueueCycleType
from core.tasks.task import Task
from orchestrator.queueing.cycle_state import QueueCycleStateStore

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = (
    "QueueCycleManager",
    "QueueCycleManagerDependencies",
)

LOGGER_NAME_ORCHESTRATOR_QUEUEING_CYCLES = "SoAI.orchestrator.queueing.cycles"
OPERATION_ORCHESTRATOR_QUEUE_CYCLES_CLOSE_PLUGIN = "orchestrator.queue_cycles.close_plugin"
OPERATION_ORCHESTRATOR_QUEUE_CYCLES_CLOSE_PRIORITY = "orchestrator.queue_cycles.close_priority"
OPERATION_ORCHESTRATOR_QUEUEING_CYCLES_OPEN_CYCLE_AND_ENQUEUE_NOWAIT = (
    "orchestrator.queueing.cycles.open_cycle_and_enqueue_nowait"
)


@dataclass(frozen=True, slots=True)
class QueueCycleManagerDependencies:
    metrics: MetricsManagerProtocol | None

    def __post_init__(self) -> None:
        require_dependencies(owner="QueueCycleManagerDependencies")


class QueueCycleManager:
    def __init__(self, deps: QueueCycleManagerDependencies) -> None:
        self._metrics = deps.metrics
        self._state = QueueCycleStateStore(deps.metrics)

    def get_open_counts(self) -> dict[str, int]:
        return self._state.get_open_counts()

    async def open_cycle_and_enqueue_nowait(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        queue: TaskDoneQueueProtocol,
        enqueue: Callable[[], None],
    ) -> None:
        try:
            await self._state.open_cycle_and_enqueue_nowait(
                task_id,
                cycle_type,
                queue,
                enqueue,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            details = {
                "task_id": task_id,
                "cycle_type": cycle_type.value,
                "queue_id": id(queue),
            }
            logger = get_logger(LOGGER_NAME_ORCHESTRATOR_QUEUEING_CYCLES)
            error = coerce_to_soai_error(
                exception,
                operation=OPERATION_ORCHESTRATOR_QUEUEING_CYCLES_OPEN_CYCLE_AND_ENQUEUE_NOWAIT,
                details=details,
            )
            log_exception(
                logger,
                error,
                message="Failed to enqueue after opening queue cycle.",
                operation=OPERATION_ORCHESTRATOR_QUEUEING_CYCLES_OPEN_CYCLE_AND_ENQUEUE_NOWAIT,
                details=details,
            )
            raise error from exception

    async def abandon_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
    ) -> bool:
        return await self._state.abandon_cycle(task_id, cycle_type)

    async def migrate_cycle(
        self,
        task_id: str,
        cycle_type: QueueCycleType,
        target_queue: TaskDoneQueueProtocol,
    ) -> None:
        source_queue = await self._state.migrate_cycle(task_id, cycle_type, target_queue)
        if source_queue is None:
            return
        self._call_task_done(
            source_queue,
            task_id,
            cycle_type,
            context_label="during queue migration",
            for_requeue=False,
        )

    async def close_cycle(
        self,
        task: Task,
        cycle_type: QueueCycleType,
        *,
        context_label: str = "",
        for_requeue: bool = False,
    ) -> bool:
        queue = await self._state.close_cycle(task.task_id, cycle_type)
        if queue is None:
            return False
        self._call_task_done(
            queue,
            task.task_id,
            cycle_type,
            context_label=context_label,
            for_requeue=for_requeue,
        )
        return True

    def _call_task_done(
        self,
        queue: TaskDoneQueueProtocol,
        task_id: str,
        cycle_type: QueueCycleType,
        *,
        context_label: str,
        for_requeue: bool,
    ) -> None:
        logger = get_logger(LOGGER_NAME_ORCHESTRATOR_QUEUEING_CYCLES)
        try:
            queue.task_done()
        except ValueError:
            if self._metrics is not None:
                self._metrics.increment_counter(*ORCHESTRATOR_COUNTER_QUEUE_DOUBLE_FINALIZATION)
            if cycle_type is QueueCycleType.PRIORITY and for_requeue:
                logger.warning(
                    "task_done() called too many times during requeue for task [%s].",
                    task_id,
                )
                return
            if cycle_type is QueueCycleType.PRIORITY:
                logger.warning(
                    "task_done() called too many times%s for task [%s].",
                    (f" {context_label}" if context_label else ""),
                    task_id,
                )
                return
            logger.warning("Queue task_done() called too many times for plugin queue dispatcher.")
        except RECOVERABLE_EXCEPTIONS as exception:
            if cycle_type is QueueCycleType.PRIORITY:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to call task_done() for orchestrator priority queue (non-critical).",
                    operation=OPERATION_ORCHESTRATOR_QUEUE_CYCLES_CLOSE_PRIORITY,
                    level="debug",
                )
            else:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to call task_done() for plugin queue dispatcher (non-critical).",
                    operation=OPERATION_ORCHESTRATOR_QUEUE_CYCLES_CLOSE_PLUGIN,
                    level="debug",
                )
