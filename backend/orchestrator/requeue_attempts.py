"""SoAI - Orchestrator requeue attempt lifecycle [backend/orchestrator/requeue_attempts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.tasks.enums import TaskStatus
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.orchestration_persistence import cache_and_persist_orchestration_state
from core.tasks.status_transitions import update_status
from core.tasks.task import Task
from orchestrator.durable_requeue import durably_requeue_task
from orchestrator.prompt_slot_lifecycle import release_prompt_slot_and_update_cache
from orchestrator.requeue_ownership import (
    close_task_queue_cycles,
    release_task_execution_ownership,
)
from orchestrator.requeue_preparation import (
    REQUEUE_BLOCKED_BY_DELIVERY_MESSAGE,
    RequeueAttemptResult,
    is_requeue_blocked_by_delivery,
    prepare_task_for_requeue,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from orchestrator.internal_protocols import OrchestratorTaskOutcomesProtocol

__all__ = (
    "RequeueAttemptSpec",
    "build_scheduler_requeue_attempt_spec",
    "execute_requeue_attempt",
)


@dataclass(frozen=True, slots=True)
class RequeueAttemptSpec:
    logger: LoggerProtocol
    operation: str
    close_priority_cycle: bool
    close_plugin_cycle: bool
    prepare_task: bool = False
    clear_parameter_snapshot: bool = False
    fail_on_failure: bool = False


def build_scheduler_requeue_attempt_spec(
    *,
    logger: LoggerProtocol,
    operation: str,
) -> RequeueAttemptSpec:
    return RequeueAttemptSpec(
        logger=logger,
        operation=operation,
        close_priority_cycle=True,
        close_plugin_cycle=True,
        prepare_task=True,
        fail_on_failure=True,
    )


async def execute_requeue_attempt(
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    spec: RequeueAttemptSpec,
    outcomes: OrchestratorTaskOutcomesProtocol | None = None,
) -> RequeueAttemptResult:
    cached_task = await task_registry.get(task.task_id)
    task = cached_task if cached_task is not None else task
    prepared_task = (
        prepare_task_for_requeue(
            task,
            clear_parameter_snapshot=spec.clear_parameter_snapshot,
        )
        if spec.prepare_task
        else task
    )
    result = await _persist_and_enqueue_requeue(
        queue,
        task_registry,
        prepared_task,
        spec=spec,
    )
    if result.requeued or not spec.fail_on_failure or result.task.status.is_terminal():
        return result
    if outcomes is None:
        raise StateError("Requeue attempt failure handling requires outcomes.")
    task_for_failure = result.task
    if result.blocked_by_delivery:
        task_for_failure = await release_task_execution_ownership(
            queue,
            task_registry,
            task_for_failure,
            close_priority_cycle=spec.close_priority_cycle,
            close_plugin_cycle=spec.close_plugin_cycle,
        )
        result = RequeueAttemptResult(
            task=task_for_failure,
            requeued=False,
            blocked_by_delivery=True,
        )
    failure_message = (
        REQUEUE_BLOCKED_BY_DELIVERY_MESSAGE
        if result.blocked_by_delivery
        else TASK_STATE_PERSISTENCE_FAILED_MESSAGE
    )
    await outcomes.fail_task(task_for_failure, failure_message, allow_failover=False)
    return result


async def _persist_and_enqueue_requeue(
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    spec: RequeueAttemptSpec,
) -> RequeueAttemptResult:
    cached_task = await task_registry.get(task.task_id)
    task = cached_task if cached_task is not None else task
    context = task.orchestration_context
    if context is not None and is_requeue_blocked_by_delivery(context):
        return RequeueAttemptResult(task=task, requeued=False, blocked_by_delivery=True)
    task, enqueue_ready = await _persist_task_for_requeue(
        queue,
        task_registry,
        task,
        spec=spec,
    )
    if not enqueue_ready:
        return RequeueAttemptResult(task=task, requeued=False, blocked_by_delivery=False)
    requeued = await durably_requeue_task(
        queue,
        task_registry,
        task,
        logger=spec.logger,
        operation=spec.operation,
    )
    return RequeueAttemptResult(task=task, requeued=requeued, blocked_by_delivery=False)


async def _persist_task_for_requeue(
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    spec: RequeueAttemptSpec,
) -> tuple[Task, bool]:
    await close_task_queue_cycles(
        queue,
        task,
        close_priority_cycle=spec.close_priority_cycle,
        close_plugin_cycle=spec.close_plugin_cycle,
    )
    success, _ = await cache_and_persist_orchestration_state(
        task_registry,
        task,
        logger=spec.logger,
        operation=spec.operation,
    )
    status_updated = False
    if success:
        updated_task = await update_status(task_registry, task.task_id, TaskStatus.QUEUED)
        if updated_task is not None:
            task = updated_task
            status_updated = not task.status.is_terminal()
        else:
            refreshed_task = await task_registry.get(task.task_id, force_refresh=True)
            if refreshed_task is not None:
                task = refreshed_task
    task = await release_prompt_slot_and_update_cache(queue.priority, task_registry, task)
    return (task, bool(success and status_updated and (not task.status.is_terminal())))
