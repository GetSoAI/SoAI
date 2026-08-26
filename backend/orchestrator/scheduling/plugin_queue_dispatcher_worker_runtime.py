"""SoAI - Plugin queue worker runtime [backend/orchestrator/scheduling/plugin_queue_dispatcher_worker_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from enum import Enum
from typing import TYPE_CHECKING

from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.errors.error_types import ErrorType
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.protocols_queue import QueueCycleType
from core.tasks.task import Task
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC, STANDARD_DELAY_SEC
from orchestrator.scheduling.internal_protocols import (
    PluginQueueDispatcherDependenciesProtocol,
)
from orchestrator.scheduling.plugin_queue_task_handler import handle_dispatched_task

if TYPE_CHECKING:
    from core.logging.rate_limited_logger import RateLimitedLogger

__all__ = (
    "PluginQueueWorkerWaitOutcome",
    "resolve_plugin_queue_worker_count",
    "run_plugin_queue_worker",
    "wait_for_queue_item",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.plugin_queue_dispatcher_worker_runtime"
OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_FAIL_RECOVERY = (
    "orchestrator.plugin_queue_dispatcher.fail_recovery"
)
OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_PROCESS_TASK = (
    "orchestrator.plugin_queue_dispatcher.process_task"
)


class PluginQueueWorkerWaitOutcome(Enum):
    TASK = "task"
    SHUTDOWN = "shutdown"
    SWAPPED = "swapped"
    IDLE = "idle"


def _resolve_recovery_error_type(error_code: str | int) -> ErrorType:
    normalized_code = str(error_code)
    for error_type in ErrorType:
        if error_type.value == normalized_code:
            return error_type
    return ErrorType.SERVER_ERROR


def resolve_plugin_queue_worker_count(
    deps: PluginQueueDispatcherDependenciesProtocol,
    plugin_name: str,
) -> int:
    limit = deps.capacity.get_plugin_limit(plugin_name)
    if limit is None:
        return 1
    if limit <= 0:
        return max(1, deps.capacity.get_plugin_queue_unlimited_workers())
    max_workers = max(1, deps.capacity.get_plugin_queue_max_workers())
    return max(1, min(int(limit), max_workers))


async def wait_for_queue_item(
    deps: PluginQueueDispatcherDependenciesProtocol,
    *,
    plugin_name: str,
    plugin_queue: asyncio.Queue[Task],
    swap_event: asyncio.Event,
    timeout: float,
) -> tuple[Task | None, PluginQueueWorkerWaitOutcome]:
    race_result = await race_queue_operation_against_signals(
        plugin_queue.get(),
        (deps.shutdown_event, swap_event),
        timeout_seconds=timeout,
    )
    if race_result.outcome is QueueRaceOutcome.OPERATION_COMPLETED:
        queue_item = race_result.value
        if queue_item is None or not isinstance(queue_item, Task):
            raise StateError(
                f"Invalid item type in plugin queue for '{plugin_name}': expected Task, got {type(queue_item).__name__ if queue_item else 'None'}",
            )
        return queue_item, PluginQueueWorkerWaitOutcome.TASK
    if race_result.outcome is QueueRaceOutcome.SIGNAL_FIRED:
        if race_result.signal_index == 0:
            return None, PluginQueueWorkerWaitOutcome.SHUTDOWN
        return None, PluginQueueWorkerWaitOutcome.SWAPPED
    state = await deps.lifecycle.watchers.get_plugin_state(plugin_name)
    queue_is_empty = await deps.capacity.is_queue_empty(plugin_name)
    if not (state and state.active_tasks) and queue_is_empty:
        return None, PluginQueueWorkerWaitOutcome.IDLE
    return None, PluginQueueWorkerWaitOutcome.SWAPPED


async def run_plugin_queue_worker(
    deps: PluginQueueDispatcherDependenciesProtocol,
    *,
    plugin_name: str,
    worker_index: int,
    stop_event: asyncio.Event,
    active_tasks_by_worker: dict[int, Task],
    requeue_warner: RateLimitedLogger,
) -> None:
    logger = get_logger(LOGGER_NAME)
    while (not deps.shutdown_event.is_set()) and (not stop_event.is_set()):
        queue_item: Task | None = None
        try:
            desired_workers = resolve_plugin_queue_worker_count(deps, plugin_name)
            if worker_index >= desired_workers:
                logger.trace(
                    "Plugin queue for '%s' worker %s stopping due to concurrency resize (desired=%s).",
                    plugin_name,
                    worker_index,
                    desired_workers,
                )
                return
            binding = await deps.capacity.get_existing_plugin_queue_binding(plugin_name)
            if binding is None:
                stop_event.set()
                return
            plugin_queue, swap_event = binding
            queue_item, wait_outcome = await wait_for_queue_item(
                deps,
                plugin_name=plugin_name,
                plugin_queue=plugin_queue,
                swap_event=swap_event,
                timeout=INTERACTIVE_TIMEOUT_SEC,
            )
            if wait_outcome is PluginQueueWorkerWaitOutcome.SHUTDOWN:
                return
            if wait_outcome is PluginQueueWorkerWaitOutcome.IDLE:
                return
            if wait_outcome is PluginQueueWorkerWaitOutcome.SWAPPED or queue_item is None:
                continue
            active_tasks_by_worker[worker_index] = queue_item
            await handle_dispatched_task(
                deps,
                plugin_name,
                queue_item,
                requeue_warner=requeue_warner,
            )
            active_tasks_by_worker.pop(worker_index, None)
        except RECOVERABLE_EXCEPTIONS as process_error:
            task_label = queue_item.task_id if queue_item is not None else "unknown"
            log_exception(
                logger,
                process_error,
                message=f"Failed to process task {task_label} in plugin queue for '{plugin_name}'",
                operation=OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_PROCESS_TASK,
            )
            if queue_item is not None:
                try:
                    coerced = coerce_to_soai_error(
                        process_error,
                        operation=OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_PROCESS_TASK,
                    )
                    refreshed_task = await deps.task_registry.get(queue_item.task_id)
                    if refreshed_task is None or not refreshed_task.status.is_terminal():
                        await deps.queue.cycles.close_cycle(queue_item, QueueCycleType.PLUGIN)
                        await deps.outcomes.fail_task(
                            queue_item,
                            coerced.message,
                            allow_failover=True,
                            error_type=_resolve_recovery_error_type(coerced.code),
                        )
                except RECOVERABLE_EXCEPTIONS as fail_error:
                    log_exception(
                        logger,
                        fail_error,
                        message=f"Could not fail task {task_label} after dispatch error for '{plugin_name}'",
                        operation=OPERATION_ORCHESTRATOR_PLUGIN_QUEUE_DISPATCHER_FAIL_RECOVERY,
                    )
            active_tasks_by_worker.pop(worker_index, None)
            await asyncio.sleep(STANDARD_DELAY_SEC)
