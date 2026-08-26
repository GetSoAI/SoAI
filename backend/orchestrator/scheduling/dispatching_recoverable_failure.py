"""SoAI - Scheduler dispatch recoverable failure resolution [backend/orchestrator/scheduling/dispatching_recoverable_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.logging.protocols import TraceLogger
from core.tasks.task import Task
from orchestrator.queueing.cycle_errors import (
    PluginQueueCycleAlreadyOpenError,
    QueueCycleAlreadyOpenError,
)
from orchestrator.scheduling.dispatch_rejections import release_dispatch_admission_ownership
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.dispatching_post_enqueue_status import (
    mark_task_dispatched_after_enqueue,
)
from orchestrator.scheduling.plugin_dispatch_readiness import (
    requeue_deferred_plugin_dispatch,
)
from orchestrator.scheduling.plugin_queue_dispatcher_start_recovery import (
    requeue_plugin_queue_after_dispatcher_start_failure,
)

__all__ = (
    "resolve_dispatch_recoverable_exception",
    "resolve_plugin_queue_full_exception",
    "resolve_queue_cycle_already_open_exception",
)

OPERATION = "orchestrator.dispatch_task_to_plugin_queue"

OPERATION_REQUEUE_QUEUE_FULL = "orchestrator.dispatch_task_to_plugin_queue.requeue_queue_full"


async def resolve_dispatch_recoverable_exception(
    *,
    deps: SchedulerDispatchingDependencies,
    task: Task,
    plugin_name: str,
    exception: Exception,
    enqueued: bool,
    logger: TraceLogger,
) -> None:
    if not enqueued:
        task = await release_dispatch_admission_ownership(deps, task)
    else:
        await requeue_plugin_queue_after_dispatcher_start_failure(
            deps=deps,
            plugin_name=plugin_name,
            logger=logger,
            exception=exception,
        )
        return
    log_exception(
        logger,
        exception,
        message="Failed to dispatch task to plugin queue.",
        operation=OPERATION,
        details={"task_id": task.task_id, "plugin": plugin_name},
        level="warning",
    )
    await deps.outcomes.fail_task(
        task,
        f"Dispatch failure: {exception}",
        allow_failover=True,
    )


async def resolve_queue_cycle_already_open_exception(
    *,
    deps: SchedulerDispatchingDependencies,
    task: Task,
    plugin_name: str,
    exception: QueueCycleAlreadyOpenError,
    enqueued: bool,
    logger: TraceLogger,
) -> None:
    if isinstance(exception, PluginQueueCycleAlreadyOpenError):
        logger.debug(
            "Skipping duplicate dispatch for task [%s] on plugin '%s' because the plugin queue cycle is already open.",
            task.task_id,
            plugin_name,
        )
        await mark_task_dispatched_after_enqueue(
            deps.task_registry,
            task,
            plugin_name=plugin_name,
        )
        return
    if not enqueued:
        task = await release_dispatch_admission_ownership(deps, task)
    log_exception(
        logger,
        exception,
        message="Failed to dispatch task to plugin queue.",
        operation=OPERATION,
        details={"task_id": task.task_id, "plugin": plugin_name},
        level="warning",
    )
    await deps.outcomes.fail_task(
        task,
        f"Dispatch failure: {exception}",
        allow_failover=True,
    )


async def resolve_plugin_queue_full_exception(
    *,
    deps: SchedulerDispatchingDependencies,
    task: Task,
    plugin_name: str,
    logger: TraceLogger,
) -> None:
    await requeue_deferred_plugin_dispatch(
        queue=deps.queue,
        task_registry=deps.task_registry,
        outcomes=deps.outcomes,
        task=task,
        logger=logger,
        operation=OPERATION_REQUEUE_QUEUE_FULL,
        warning_message=(
            "Plugin queue backpressure for task [%s] on plugin '%s'. "
            "Returning task to scheduler-backed queue."
        ),
        warning_args=(task.task_id, plugin_name),
        warner=None,
    )
