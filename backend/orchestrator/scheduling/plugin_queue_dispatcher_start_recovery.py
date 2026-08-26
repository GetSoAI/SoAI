"""SoAI - Plugin queue dispatcher start failure recovery [backend/orchestrator/scheduling/plugin_queue_dispatcher_start_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from orchestrator.requeue_attempts import RequeueAttemptSpec, execute_requeue_attempt

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from orchestrator.scheduling.dispatching_dependencies import (
        SchedulerDispatchingDependencies,
    )

__all__ = ("requeue_plugin_queue_after_dispatcher_start_failure",)

OPERATION_REQUEUE_AFTER_DISPATCHER_START_FAILURE = (
    "orchestrator.dispatch_task_to_plugin_queue.dispatcher_start_failed_requeue"
)


async def requeue_plugin_queue_after_dispatcher_start_failure(
    *,
    deps: SchedulerDispatchingDependencies,
    plugin_name: str,
    logger: TraceLogger,
    exception: Exception,
) -> None:
    log_exception(
        logger,
        exception,
        message="Plugin queue dispatcher failed to start after task enqueue; draining plugin queue back to scheduler.",
        operation=OPERATION_REQUEUE_AFTER_DISPATCHER_START_FAILURE,
        details={"plugin": plugin_name},
        level="warning",
    )
    drained_tasks = await deps.capacity.drain_plugin_queue(plugin_name)
    for drained_task in drained_tasks:
        await execute_requeue_attempt(
            deps.queue,
            deps.task_registry,
            drained_task,
            spec=RequeueAttemptSpec(
                logger=logger,
                operation=OPERATION_REQUEUE_AFTER_DISPATCHER_START_FAILURE,
                close_priority_cycle=True,
                close_plugin_cycle=False,
                prepare_task=True,
                fail_on_failure=True,
            ),
            outcomes=deps.outcomes,
        )
