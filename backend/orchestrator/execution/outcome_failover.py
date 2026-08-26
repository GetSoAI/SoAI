"""SoAI - Failover handling for task outcomes [backend/orchestrator/execution/outcome_failover.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.logging.trace import get_logger
from core.tasks.orchestration_context_cache import merge_orchestration_context_snapshot
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from orchestrator.internal_protocols import TransientFailureCooldownsProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.model_info_resolution import resolve_orchestrator_model
from orchestrator.queueing.execution_plan_context import apply_primary_model_context
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.requeue_attempts import RequeueAttemptSpec, execute_requeue_attempt
from orchestrator.requeue_ownership import release_task_execution_ownership
from orchestrator.requeue_preparation import (
    RequeueAttemptResult,
    is_requeue_blocked_by_delivery,
    prepare_task_for_requeue,
)

__all__ = (
    "requeue_failover_task",
    "try_failover_task",
)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_failover"


async def try_failover_task(
    queue: QueueServiceView,
    lifecycle: OrchestratorLifecycleCoordinatorProtocol,
    transient_failures: TransientFailureCooldownsProtocol,
    task: Task,
) -> tuple[Task, bool]:
    logger = get_logger(LOGGER_NAME)
    context = queue.require_orchestration_context(task)
    if is_requeue_blocked_by_delivery(context):
        return (task, False)
    virtual_model_name = context.virtual_model_name
    if not virtual_model_name:
        return (task, False)
    virtual_model_map = await lifecycle.startup.get_virtual_model_map()
    virtual_model_config = virtual_model_map.get(virtual_model_name)
    if not (
        virtual_model_config and virtual_model_config.strategy in {"failover", "load_balancing"}
    ):
        return (task, False)
    if context.execution_universal_ids:
        failed_universal_id = context.execution_universal_ids[0]
        remaining_universal_ids = context.execution_universal_ids[1:]
        context = replace(
            context,
            execution_universal_ids=remaining_universal_ids,
            excluded_universal_ids=context.excluded_universal_ids
            | frozenset({failed_universal_id}),
        )
        task = task.with_orchestration_context(context)
        task = await merge_orchestration_context_snapshot(queue.task_registry, task)
        if task.status.is_terminal():
            await queue.execution_reservations.release(context.tracking_id)
            return (task, False)
        transient_failures.record(failed_universal_id)
        logger.warning(
            "Task [%s] failed on model [%s], marking transient failure.",
            task.task_id,
            failed_universal_id,
        )
    task = await _prepare_next_failover_task(queue, transient_failures, task)
    if task.status.is_terminal():
        return (task, False)
    context = queue.require_orchestration_context(task)
    if context.execution_universal_ids:
        logger.warning(
            "Task [%s] failed, attempting immediate failover. New plan: %s",
            task.task_id,
            list(context.execution_universal_ids),
        )
        return (task, True)
    return (task, False)


async def _prepare_next_failover_task(
    queue: QueueServiceView,
    transient_failures: TransientFailureCooldownsProtocol,
    task: Task,
) -> Task:
    while True:
        context = queue.require_orchestration_context(task)
        if task.status.is_terminal():
            await queue.execution_reservations.release(context.tracking_id)
            return task
        if not context.execution_universal_ids:
            await queue.execution_reservations.release(context.tracking_id)
            return task
        next_universal_id = context.execution_universal_ids[0]
        if transient_failures.is_on_cooldown(next_universal_id):
            context = replace(
                context,
                execution_universal_ids=context.execution_universal_ids[1:],
                excluded_universal_ids=context.excluded_universal_ids
                | frozenset({next_universal_id}),
            )
            task = task.with_orchestration_context(context)
            task = await merge_orchestration_context_snapshot(queue.task_registry, task)
            continue
        resolved_model, _ = await resolve_orchestrator_model(
            queue.orchestrator_deps.model_information_service,
            next_universal_id,
            require_canonical_universal_id=False,
        )
        if resolved_model is not None:
            task = prepare_task_for_requeue(task, clear_parameter_snapshot=True)
            context = queue.require_orchestration_context(task)
            task, _ = await apply_primary_model_context(queue, task, context, resolved_model)
            await queue.execution_reservations.reserve(
                context.tracking_id,
                next_universal_id,
            )
            task = await merge_orchestration_context_snapshot(queue.task_registry, task)
            if task.status.is_terminal():
                continue
            return task
        context = replace(
            context,
            execution_universal_ids=context.execution_universal_ids[1:],
            excluded_universal_ids=context.excluded_universal_ids | frozenset({next_universal_id}),
        )
        task = task.with_orchestration_context(context)
        task = await merge_orchestration_context_snapshot(queue.task_registry, task)


async def requeue_failover_task(
    queue: QueueServiceView,
    task_registry: TaskRegistryProtocol,
    task: Task,
) -> RequeueAttemptResult:
    logger = get_logger(LOGGER_NAME)
    cached_task = await task_registry.get(task.task_id)
    task = cached_task if cached_task is not None else task
    context = task.orchestration_context
    if context is not None and is_requeue_blocked_by_delivery(context):
        task = await release_task_execution_ownership(
            queue,
            task_registry,
            task,
            close_priority_cycle=True,
            close_plugin_cycle=True,
        )
        return RequeueAttemptResult(task=task, requeued=False, blocked_by_delivery=True)
    requeue_result = await execute_requeue_attempt(
        queue,
        task_registry,
        task,
        spec=RequeueAttemptSpec(
            logger=logger,
            operation="orchestrator.failover_requeue",
            close_priority_cycle=True,
            close_plugin_cycle=True,
        ),
    )
    return requeue_result
