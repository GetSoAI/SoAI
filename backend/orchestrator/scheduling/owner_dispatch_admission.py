"""SoAI - Owner capacity admission before plugin queue handoff [backend/orchestrator/scheduling/owner_dispatch_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.logging.protocols import TraceLogger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
    SchedulerWorkItem,
)
from core.tasks.enums import TaskStatus
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.orchestration_persistence import persist_with_logging
from core.tasks.status_policy import RUNNING_TASK_STATUS_VALUES
from core.tasks.status_transitions import update_status
from core.tasks.task import Task
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from orchestrator.scheduling.dispatch_rejections import fail_released_dispatch_task
from orchestrator.scheduling.dispatching_dependencies import SchedulerDispatchingDependencies

__all__ = ("admit_owner_dispatch",)


async def admit_owner_dispatch(
    deps: SchedulerDispatchingDependencies,
    task: Task,
    plugin_name: str,
    logger: TraceLogger,
) -> Task | None:
    current_task = await deps.task_registry.get(task.task_id)
    if current_task is None:
        raise StateError("Dispatch admission requires a registered task.")
    task = current_task
    inference_task = is_orchestrated_inference_task_type(task.task_type)
    if inference_task and (
        task.status.is_terminal()
        or task.status == TaskStatus.DEDUPED
        or task.status.value in RUNNING_TASK_STATUS_VALUES
    ):
        return None
    if inference_task and task.status not in (TaskStatus.QUEUED, TaskStatus.AWAITING_SCHEDULER):
        raise StateError("Dispatch admission requires a queued inference task.")
    success, _ = await persist_with_logging(
        deps.task_registry,
        task.task_id,
        logger=logger,
        operation="orchestrator.dispatch_task_to_plugin",
    )
    if not success:
        await fail_released_dispatch_task(
            deps, task, TASK_STATE_PERSISTENCE_FAILED_MESSAGE, allow_failover=False
        )
        return None
    if not inference_task:
        return task
    if await deps.queue.is_task_cancelled(task):
        await deps.outcomes.cancel_task(task, "Task cancelled before dispatch.")
        return None
    routing_config = deps.queue.routing_config
    owner_limit = routing_config.owner_running_limits_by_owner_type.get(
        task.owner_type, routing_config.owner_running_limits_default
    )
    if owner_limit > 0:
        running_count = await deps.task_registry.database_tasks.count_running_orchestrated_inference_tasks_for_owner(
            task.owner_type, task.owner_id
        )
        if running_count >= owner_limit:
            context = task.require_orchestration_context()
            routing_key = context.routing_key
            if not routing_key and context.execution_universal_ids:
                routing_key = context.execution_universal_ids[0]
            if not routing_key:
                raise StateError("Owner admission deferral requires a routing key.")
            await deps.queue.mark_task_pending(task, routing_key, plugin_name=plugin_name)
            await deps.queue.tracking.set_deferral_reason(
                routing_key,
                f"Owner running limit reached for {task.owner_type}:{task.owner_id} ({running_count}/{owner_limit}).",
            )
            await deps.queue_scheduler_work(
                SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY, routing_key)
            )
            return None
    admitted_task = await update_status(deps.task_registry, task.task_id, TaskStatus.DISPATCHED)
    if admitted_task is None:
        refreshed_task = await deps.task_registry.get(task.task_id, force_refresh=True)
        if refreshed_task is not None and refreshed_task.status.is_terminal():
            return None
        await fail_released_dispatch_task(
            deps, task, TASK_STATE_PERSISTENCE_FAILED_MESSAGE, allow_failover=False
        )
    return admitted_task
