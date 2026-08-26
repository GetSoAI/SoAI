"""SoAI - Plugin queue shutdown finalization for scheduler dispatching [backend/orchestrator/scheduling/dispatch_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import Enum

from core.concurrency.protocols import QueueGetNowaitProtocol
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.protocols_queue import QueueCycleType
from core.runtime.shutdown_errors import SERVER_SHUTTING_DOWN_MESSAGE
from core.tasks.task import Task
from orchestrator.requeue_attempts import (
    build_scheduler_requeue_attempt_spec,
    execute_requeue_attempt,
)
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.purge_state import PurgeStateSnapshot

__all__ = (
    "fail_purged_dispatch",
    "finalize_plugin_queue_shutdown",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.dispatch_shutdown"
OPERATION = "orchestrator.scheduler.finalize_plugin_queue_shutdown"


class _TaskFinalizationOutcome(Enum):
    TERMINAL = "terminal"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REQUEUED = "requeued"
    UNCHANGED = "unchanged"


async def fail_purged_dispatch(
    *,
    task: Task,
    plugin_name: str,
    purge_snapshot: PurgeStateSnapshot,
    deps: SchedulerDispatchingDependencies,
) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.warning(
        "Rejecting dispatch of task [%s] for plugin '%s' because purge is active: %s",
        task.task_id,
        plugin_name,
        purge_snapshot.reason,
    )
    await deps.outcomes.fail_task(
        task,
        purge_snapshot.reason,
        allow_failover=purge_snapshot.allow_failover,
    )


async def finalize_plugin_queue_shutdown(
    *,
    plugin_name: str,
    queue: QueueGetNowaitProtocol[Task] | None,
    active_tasks: list[Task],
    deps: SchedulerDispatchingDependencies,
    snapshot_purge_state: Callable[[str], Awaitable[PurgeStateSnapshot]],
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
    dispatcher_lock: asyncio.Lock,
) -> None:
    logger = get_logger(LOGGER_NAME)
    shutdown_in_progress = deps.shutdown_event.is_set()
    purge_snapshot = await snapshot_purge_state(plugin_name)
    should_finalize_terminal = shutdown_in_progress or purge_snapshot.is_purging
    failure_reason = SERVER_SHUTTING_DOWN_MESSAGE if shutdown_in_progress else purge_snapshot.reason
    should_allow_failover = (not shutdown_in_progress) and purge_snapshot.allow_failover
    registry = deps.task_registry

    async def _finalize_task_item(task_item: Task) -> _TaskFinalizationOutcome:
        refreshed_task = await registry.get(task_item.task_id, force_refresh=True)
        resolved_task = refreshed_task if refreshed_task is not None else task_item
        if resolved_task.status.is_terminal():
            await deps.queue.cycles.close_cycle(resolved_task, QueueCycleType.PLUGIN)
            return _TaskFinalizationOutcome.TERMINAL
        if shutdown_in_progress:
            await deps.queue.cycles.close_cycle(resolved_task, QueueCycleType.PLUGIN)
            await deps.outcomes.cancel_task(resolved_task, failure_reason)
            return _TaskFinalizationOutcome.CANCELLED
        if should_finalize_terminal:
            await deps.queue.cycles.close_cycle(resolved_task, QueueCycleType.PLUGIN)
            await deps.outcomes.fail_task(
                resolved_task,
                failure_reason,
                allow_failover=should_allow_failover,
            )
            return _TaskFinalizationOutcome.FAILED
        requeue_result = await execute_requeue_attempt(
            deps.queue,
            registry,
            resolved_task,
            spec=build_scheduler_requeue_attempt_spec(
                logger=logger,
                operation="orchestrator.scheduler.dispatch_shutdown_requeue",
            ),
            outcomes=deps.outcomes,
        )
        if requeue_result.requeued:
            return _TaskFinalizationOutcome.REQUEUED
        return _TaskFinalizationOutcome.UNCHANGED

    requeued = 0
    cancelled = 0
    failed = 0
    for active_task in active_tasks:
        try:
            outcome = await _finalize_task_item(active_task)
            if outcome is _TaskFinalizationOutcome.FAILED:
                failed += 1
            elif outcome is _TaskFinalizationOutcome.CANCELLED:
                cancelled += 1
            elif outcome is _TaskFinalizationOutcome.REQUEUED:
                requeued += 1
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=(
                    "Failed to finalize active task while shutting down plugin queue dispatcher."
                ),
                operation=OPERATION,
                details={"task_id": active_task.task_id, "plugin": plugin_name},
                level="warning",
            )
    if queue:
        while True:
            try:
                queue_item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            try:
                outcome = await _finalize_task_item(queue_item)
                if outcome is _TaskFinalizationOutcome.FAILED:
                    failed += 1
                elif outcome is _TaskFinalizationOutcome.CANCELLED:
                    cancelled += 1
                elif outcome is _TaskFinalizationOutcome.REQUEUED:
                    requeued += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to finalize task while shutting down plugin queue dispatcher.",
                    operation=OPERATION,
                    details={"task_id": queue_item.task_id, "plugin": plugin_name},
                    level="warning",
                )
    if requeued:
        logger.warning(
            (
                "Re-queued %s stranded tasks from '%s' plugin queue after dispatcher "
                "stopped unexpectedly."
            ),
            requeued,
            plugin_name,
        )
    if failed:
        logger.warning(
            "Failed %s stranded tasks from '%s' plugin queue: %s",
            failed,
            plugin_name,
            failure_reason,
        )
    if cancelled:
        logger.info(
            "Cancelled %s stranded tasks from '%s' plugin queue: %s",
            cancelled,
            plugin_name,
            failure_reason,
        )
    current_task = asyncio.current_task()
    async with dispatcher_lock:
        registered_dispatcher = plugin_queue_dispatchers.get(plugin_name)
        if registered_dispatcher is current_task:
            plugin_queue_dispatchers.pop(plugin_name, None)
