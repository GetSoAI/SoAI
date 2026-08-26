"""SoAI - Orchestrator durable task requeue persistence [backend/orchestrator/durable_requeue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from orchestrator.internal_protocols import OrchestratorTaskOutcomesProtocol

__all__ = (
    "durably_requeue_or_release_after_plugin_purge",
    "durably_requeue_task",
)


async def durably_requeue_task(
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    logger: LoggerProtocol,
    operation: str,
    notify_wakeup: bool = True,
    available_at_ms: int | None = None,
    status_message: str | None = None,
    failure_message: str = "Failed to durably requeue orchestrated task.",
) -> bool:
    resolved_available_at_ms = epoch_ms() if available_at_ms is None else available_at_ms
    try:
        requeued = await task_registry.database_tasks.requeue_orchestrated_inference_task(
            task.task_id,
            available_at_ms=resolved_available_at_ms,
            status_message=status_message,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=failure_message,
            operation=operation,
            details={"task_id": task.task_id},
            level="warning",
        )
        return False
    if not requeued:
        return False
    await queue.tracking.forget_task(task.task_id)
    if notify_wakeup:
        queue.notify_durable_queue_wakeup()
    return True


async def durably_requeue_or_release_after_plugin_purge(
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    outcomes: OrchestratorTaskOutcomesProtocol,
    logger: LoggerProtocol,
    operation: str,
    allow_failover: bool,
    available_at_ms: int,
) -> bool:
    if task.status.is_terminal():
        await queue.tracking.forget_task(task.task_id)
        return False
    requeued = await durably_requeue_task(
        queue,
        task_registry,
        task,
        logger=logger,
        operation=operation,
        notify_wakeup=False,
        available_at_ms=available_at_ms,
        failure_message="Plugin queue purge failed to durably requeue task.",
    )
    if requeued:
        return True
    try:
        released = await task_registry.database_tasks.release_orchestrator_queue_item_lease(
            task.task_id,
            available_at_ms=available_at_ms,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Plugin queue purge failed to release durable lease for task.",
            operation=operation,
            details={"task_id": task.task_id},
            level="warning",
        )
        released = False
    if released:
        await queue.tracking.forget_task(task.task_id)
        return True
    await queue.tracking.forget_task(task.task_id)
    await outcomes.fail_task(
        task=task,
        reason="Plugin purge could not requeue task (durable requeue and lease release failed).",
        allow_failover=allow_failover,
    )
    return False
