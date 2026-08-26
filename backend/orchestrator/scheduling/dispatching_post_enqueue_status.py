"""SoAI - Scheduler post-enqueue dispatched status handling [backend/orchestrator/scheduling/dispatching_post_enqueue_status.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.status_transitions import update_status
from core.tasks.task import Task

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("mark_task_dispatched_after_enqueue",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.dispatching_post_enqueue_status"
OPERATION_ORCHESTRATOR_DISPATCH_TASK_TO_PLUGIN_QUEUE_POST_ENQUEUE_REFRESH = (
    "orchestrator.dispatch_task_to_plugin_queue.post_enqueue_refresh"
)
OPERATION_ORCHESTRATOR_DISPATCH_TASK_TO_PLUGIN_QUEUE_POST_ENQUEUE_STATUS = (
    "orchestrator.dispatch_task_to_plugin_queue.post_enqueue_status"
)


async def mark_task_dispatched_after_enqueue(
    registry: TaskRegistryProtocol,
    task: Task,
    *,
    plugin_name: str,
) -> Task:
    logger = get_logger(LOGGER_NAME)
    try:
        updated = await update_status(registry, task.task_id, TaskStatus.DISPATCHED)
    except RECOVERABLE_EXCEPTIONS as exception:
        refreshed = await _refresh_task_after_post_enqueue_failure(
            registry,
            task.task_id,
            logger=logger,
            plugin_name=plugin_name,
        )
        if refreshed is not None and _is_safe_post_enqueue_status(refreshed.status):
            logger.debug(
                "Post-enqueue dispatched status update skipped for task [%s] on '%s' because task is already in status '%s'.",
                task.task_id,
                plugin_name,
                refreshed.status.value,
            )
            return refreshed
        log_exception(
            logger,
            exception,
            message="Post-enqueue dispatched status update failed; allowing task to continue.",
            operation=OPERATION_ORCHESTRATOR_DISPATCH_TASK_TO_PLUGIN_QUEUE_POST_ENQUEUE_STATUS,
            details={"task_id": task.task_id, "plugin": plugin_name},
            level="warning",
        )
        return refreshed if refreshed is not None else task
    if updated is not None:
        return updated
    refreshed = await _refresh_task_after_post_enqueue_failure(
        registry,
        task.task_id,
        logger=logger,
        plugin_name=plugin_name,
    )
    if refreshed is not None and _is_safe_post_enqueue_status(refreshed.status):
        return refreshed
    logger.warning(
        "Post-enqueue dispatched status update returned no task for [%s] on '%s'. Task continues with status '%s'.",
        task.task_id,
        plugin_name,
        refreshed.status.value if refreshed is not None else task.status.value,
    )
    return refreshed if refreshed is not None else task


async def _refresh_task_after_post_enqueue_failure(
    registry: TaskRegistryProtocol,
    task_id: str,
    *,
    logger: LoggerProtocol,
    plugin_name: str,
) -> Task | None:
    try:
        return await registry.get(task_id, force_refresh=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Post-enqueue task refresh failed; allowing task to continue.",
            operation=OPERATION_ORCHESTRATOR_DISPATCH_TASK_TO_PLUGIN_QUEUE_POST_ENQUEUE_REFRESH,
            details={"task_id": task_id, "plugin": plugin_name},
            level="warning",
        )
        return None


def _is_safe_post_enqueue_status(status: TaskStatus) -> bool:
    return status in {
        TaskStatus.QUEUED,
        TaskStatus.AWAITING_SCHEDULER,
        TaskStatus.DISPATCHED,
        TaskStatus.WORKING,
        TaskStatus.PROCESSING,
        TaskStatus.INPUT_REQUIRED,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    }
