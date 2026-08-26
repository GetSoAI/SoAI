"""SoAI - Task queue enqueue, dequeue, drain, and resize operations [backend/orchestrator/queueing/priority/queue_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.concurrency.swappable_resource import SwappableResource
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ServiceUnavailableError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_base import DIRECTOR_GAUGE_QUEUE_SIZE
from core.metrics.protocols import MetricsManagerProtocol
from core.orchestrator.protocols_queue import QueueCycleManagerProtocol, QueueCycleType
from core.orchestrator.request_priority import RequestPriority
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from orchestrator.queueing.inference_priority_queue import InferencePriorityQueue
from orchestrator.queueing.priority.metrics import (
    ModelMetricsRegistry,
    record_priority_queue_enqueue_metrics,
)
from orchestrator.queueing.priority.queue_capacity import QueueCapacityLimiter
from orchestrator.queueing.priority.sentinel import ShutdownSentinel

if TYPE_CHECKING:
    type TaskQueueItem = Task | type[ShutdownSentinel]

__all__ = ("TaskQueueState",)

OPERATION_ORCHESTRATOR_QUEUEING_PRIORITY_QUEUE_OPERATIONS_PUT_WITH_TIMEOUT = (
    "orchestrator.queueing.priority.queue_operations.put_with_timeout"
)


LOGGER_NAME = "SoAI.orchestrator.queueing.queue_operations"


def _resolve_queue_item_task(item: TaskQueueItem) -> Task | None:
    return item if isinstance(item, Task) else None


class TaskQueueState:
    def __init__(
        self,
        *,
        initial_max_size: int,
        metrics: MetricsManagerProtocol | None,
        cycles: QueueCycleManagerProtocol,
        shutdown_event: asyncio.Event,
        get_total_backlog_size: Callable[[], Awaitable[int]],
        require_orchestration_context: Callable[[Task], OrchestrationContext],
        model_metrics_registry: ModelMetricsRegistry,
    ) -> None:
        self._metrics = metrics
        self._cycles = cycles
        self._shutdown_event = shutdown_event
        self._get_total_backlog_size = get_total_backlog_size
        self._require_orchestration_context = require_orchestration_context
        self._model_metrics_registry = model_metrics_registry
        self.max_size = initial_max_size
        queue: InferencePriorityQueue[TaskQueueItem] = InferencePriorityQueue(
            resolve_task=_resolve_queue_item_task,
        )
        self.queue_resource = SwappableResource(queue)
        self._capacity_limiter = QueueCapacityLimiter(limit=initial_max_size)

    def apply_runtime_config(self, queue_max_size: int) -> None:
        logger = get_logger(LOGGER_NAME)
        normalized_queue_max_size = max(int(queue_max_size), 0)
        self.max_size = normalized_queue_max_size
        if self._capacity_limiter.limit == normalized_queue_max_size:
            return
        current_occupancy = self.queue_resource.current.qsize()
        if normalized_queue_max_size and normalized_queue_max_size < current_occupancy:
            logger.warning(
                "Task queue currently holds %s items. Cannot shrink capacity below occupancy; using %s.",
                current_occupancy,
                current_occupancy,
            )
            normalized_queue_max_size = current_occupancy
            self.max_size = normalized_queue_max_size
        self._capacity_limiter.update_limit(normalized_queue_max_size)
        if normalized_queue_max_size:
            logger.debug(
                "Task queue max size updated to %s.",
                normalized_queue_max_size,
            )
        else:
            logger.debug("Task queue max size updated to unbounded.")

    def priority_counts(self) -> dict[RequestPriority, int]:
        return self.queue_resource.current.priority_counts()

    async def drain(self) -> list[Task]:
        drained: list[Task] = []
        shutdown_sentinel_count = 0
        queue = self.queue_resource.current
        while True:
            try:
                item = queue.get_nowait()
                if item is ShutdownSentinel:
                    queue.task_done()
                    shutdown_sentinel_count += 1
                elif isinstance(item, Task):
                    self._capacity_limiter.on_task_dequeued()
                    await self._cycles.close_cycle(item, QueueCycleType.PRIORITY)
                    drained.append(item)
            except asyncio.QueueEmpty:
                break
        for _ in range(shutdown_sentinel_count):
            queue.put_nowait(ShutdownSentinel)
        return drained

    def signal_shutdown(self, worker_count: int) -> None:
        if worker_count <= 0:
            return
        queue = self.queue_resource.current
        for _ in range(worker_count):
            queue.put_nowait(ShutdownSentinel)

    async def _put_with_timeout(
        self,
        task: Task,
        *,
        timeout_seconds: float,
        log_message: str,
        operation: str,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        permit = None
        try:
            permit = await self._capacity_limiter.acquire_enqueue_permission(
                timeout_seconds=timeout_seconds,
            )
            queue = self.queue_resource.current
            try:
                await self._cycles.open_cycle_and_enqueue_nowait(
                    task.task_id,
                    QueueCycleType.PRIORITY,
                    queue,
                    lambda: queue.put_nowait(task),
                )
            except asyncio.CancelledError:
                if permit is not None:
                    permit.rollback()
                raise
            except RECOVERABLE_EXCEPTIONS as exception:
                if permit is not None:
                    permit.rollback()
                log_handled_exception(
                    logger,
                    coerce_to_soai_error(
                        exception,
                        operation=operation,
                        details={"task_id": task.task_id},
                    ),
                    message="Failed to enqueue task; rolled back queue capacity permission (non-critical).",
                    operation=OPERATION_ORCHESTRATOR_QUEUEING_PRIORITY_QUEUE_OPERATIONS_PUT_WITH_TIMEOUT,
                    details={"task_id": task.task_id},
                    level="debug",
                )
                raise
            if permit is not None:
                permit.commit_enqueued()
            else:
                self._capacity_limiter.on_task_enqueued()
        except TimeoutError as exception:
            log_exception(
                logger,
                exception,
                message=log_message,
                operation=OPERATION_ORCHESTRATOR_QUEUEING_PRIORITY_QUEUE_OPERATIONS_PUT_WITH_TIMEOUT,
                details={"task_id": task.task_id},
            )
            raise ServiceUnavailableError("Task queue is full or blocked") from exception
        except (asyncio.QueueFull, RuntimeError) as exception:
            raise ServiceUnavailableError("Task queue is full or blocked") from exception

    async def enqueue(self, task: Task) -> None:
        logger = get_logger(LOGGER_NAME)
        context = self._require_orchestration_context(task)
        event = context.event
        model_name = "unknown"
        trace_id = task.task_id
        if event is not None:
            model_value = event.payload.get("model")
            model_name = model_value if isinstance(model_value, str) else "unknown"
            trace_id_value = event.context.trace_id
            trace_id = (
                trace_id_value
                if isinstance(trace_id_value, str) and trace_id_value
                else task.task_id
            )
        await self._put_with_timeout(
            task,
            timeout_seconds=10.0,
            log_message="Task could not be queued: queue full or blocked.",
            operation="orchestrator_queue.enqueue_task",
        )
        backlog = await self._get_total_backlog_size()
        logger.debug(
            "Task [%s] for model '%s' received. Queue size: %s",
            trace_id,
            model_name,
            backlog,
        )
        if self._metrics:
            record_priority_queue_enqueue_metrics(
                self._metrics,
                self._model_metrics_registry,
                context,
                backlog,
            )

    async def take(self) -> Task | None:
        while True:
            binding = self.queue_resource.bind()
            queue_obj = binding.resource
            swap_event = binding.swap_event
            if self._shutdown_event.is_set():
                return None
            try:
                item = queue_obj.get_nowait()
            except asyncio.QueueEmpty as queue_empty_error:
                race_result = await race_queue_operation_against_signals(
                    queue_obj.get(),
                    (self._shutdown_event, swap_event),
                    timeout_seconds=None,
                )
                if race_result.outcome is QueueRaceOutcome.SIGNAL_FIRED:
                    if race_result.signal_index == 0:
                        return None
                    continue
                if race_result.outcome is not QueueRaceOutcome.OPERATION_COMPLETED:
                    raise StateError(
                        "Unexpected queue race outcome while awaiting task queue item.",
                        operation="orchestrator_queue.take",
                    ) from queue_empty_error
                item_value = race_result.value
                if item_value is None:
                    raise StateError(
                        "Task queue returned an empty item; this indicates a corrupted task queue.",
                        operation="orchestrator_queue.take",
                    ) from queue_empty_error
                item = item_value
            break
        if isinstance(item, type):
            queue_obj.task_done()
            if item is ShutdownSentinel:
                if self._metrics:
                    backlog = await self._get_total_backlog_size()
                    self._metrics.set_gauge(*DIRECTOR_GAUGE_QUEUE_SIZE, value=backlog)
                return None
            raise StateError(
                "Unexpected queue sentinel type; this indicates a corrupted task queue.",
                operation="orchestrator_queue.take",
            )
        task = item
        self._capacity_limiter.on_task_dequeued()
        if self._metrics:
            backlog = await self._get_total_backlog_size()
            self._metrics.set_gauge(*DIRECTOR_GAUGE_QUEUE_SIZE, value=backlog)
        return task
