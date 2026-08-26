"""SoAI - Task queue execution plan application [backend/orchestrator/queueing/execution_plans.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.errors.exceptions import StateError
from core.events.bus_dispatch_logging import resolve_event_trace_id
from core.logging.trace import get_logger
from core.orchestrator.execution_plan import (
    DEFAULT_NO_VALID_MODELS_REASON,
    EXECUTION_PLAN_STATUS_AVAILABLE,
    EXECUTION_PLAN_STATUS_UNAVAILABLE,
    ExecutionPlan,
    resolve_execution_plan_failure_reason,
)
from core.orchestrator.queue_decisions import (
    QueueDecision,
    build_dispatch_candidate_decision,
    build_fail_task_decision,
    build_persistence_failed_task_decision,
    build_schedule_work_decision,
)
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
    SchedulerWorkItem,
)
from core.tasks.orchestration_persistence import cache_and_persist_orchestration_state
from core.tasks.task import Task
from orchestrator.execution.event_context import is_streaming_request
from orchestrator.queueing.deferred_task_context_repair import (
    try_repair_deferred_task_context,
)
from orchestrator.queueing.execution_plan_context import (
    build_available_execution_plan_context,
)
from orchestrator.queueing.execution_plan_deduplication import (
    apply_execution_plan_deduplication,
)
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.queueing.pending_registration import register_scheduler_pending_task

__all__ = ("apply_execution_plan",)

LOGGER_NAME = "SoAI.orchestrator.queueing.execution_plans"


async def apply_execution_plan(
    queue: QueueServiceView,
    task: Task,
    plan: ExecutionPlan,
) -> list[QueueDecision]:
    logger = get_logger(LOGGER_NAME)
    decisions: list[QueueDecision] = []
    if plan is None:
        raise StateError("Execution plan missing for enqueue event.")
    context = task.require_orchestration_context()
    event = context.event
    if event is None:
        raise StateError("Task missing inference event for execution plan.")
    registry = queue.task_registry
    if plan["status"] == EXECUTION_PLAN_STATUS_UNAVAILABLE:
        await queue.execution_reservations.release(context.tracking_id)
        await queue.tracking.index_task(task)
        reason = resolve_execution_plan_failure_reason(
            plan,
            default_reason=DEFAULT_NO_VALID_MODELS_REASON,
        )
        decisions.append(
            build_fail_task_decision(
                task=task,
                reason=reason,
                allow_failover=False,
            ),
        )
        return decisions
    if plan["status"] != EXECUTION_PLAN_STATUS_AVAILABLE:
        await queue.execution_reservations.release(context.tracking_id)
        deferral_key = plan.get("deferral_key")
        if not isinstance(deferral_key, str) or not deferral_key:
            raise StateError("Execution plan missing deferral key for deferred task.")
        virtual_model_name = plan.get("virtual_model_name")
        if isinstance(virtual_model_name, str) and virtual_model_name:
            logger.debug(
                "Task [%s] for virtual model '%s' deferred due to backend cooldown.",
                task.task_id,
                virtual_model_name,
            )
        else:
            logger.debug("Task [%s] deferred due to backend cooldown.", task.task_id)
        context = replace(context, virtual_model_name=virtual_model_name)
        if not context.execution_universal_ids:
            repair_result = await try_repair_deferred_task_context(
                queue,
                task,
                context,
                deferral_key=deferral_key,
                logger=logger,
                operation="orchestrator.queue.defer.persist_repair_context",
            )
            task = repair_result.task
            context = repair_result.context
        task = task.with_orchestration_context(context)
        task = await register_scheduler_pending_task(
            queue,
            task,
            deferral_key,
            plugin_name=None,
            insert_left=False,
            refresh_before_transition=False,
            index_task=True,
            register_active=True,
        )
        decisions.append(
            build_schedule_work_decision(
                SchedulerWorkItem(
                    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
                    deferral_key,
                ),
            ),
        )
        return decisions
    plan_context = await build_available_execution_plan_context(queue, task, plan)
    task = plan_context.task
    context = plan_context.context
    if not context.execution_universal_ids:
        await queue.execution_reservations.release(context.tracking_id)
        decisions.append(
            build_fail_task_decision(
                task=task,
                reason="Execution plan returned no models to try.",
                allow_failover=False,
            ),
        )
        return decisions
    if plan_context.error_reason is not None or plan_context.resolved_model is None:
        await queue.execution_reservations.release(context.tracking_id)
        decisions.append(
            build_fail_task_decision(
                task=task,
                reason=plan_context.error_reason or "Model info for execution plan is invalid.",
                allow_failover=False,
            ),
        )
        return decisions
    resolved_model = plan_context.resolved_model
    universal_id_to_try = resolved_model.universal_id
    is_streaming = is_streaming_request(context)
    dedup_hash: str | None = None
    if queue.deduplication.enabled and (not is_streaming):
        dedup_hash = queue.deduplication.calculate_dedup_hash(
            context,
            routing_config=queue.routing_config,
        )
        context = replace(context, dedup_hash=dedup_hash)
        task = task.with_orchestration_context(context)
    persisted, _ = await cache_and_persist_orchestration_state(
        registry,
        task,
        logger=logger,
        operation="orchestrator.queue.apply_execution_plan.persist_context",
        trace_id=resolve_event_trace_id(event),
    )
    if not persisted:
        await queue.execution_reservations.release(context.tracking_id)
        decisions.append(build_persistence_failed_task_decision(task))
        return decisions
    dedup_task, dedup_decisions = await apply_execution_plan_deduplication(
        queue=queue,
        task=task,
        dedup_hash=dedup_hash,
        is_streaming=is_streaming,
        logger=logger,
    )
    decisions.extend(dedup_decisions)
    if dedup_task is None:
        return decisions
    task = dedup_task
    decisions.append(
        build_dispatch_candidate_decision(
            task=task,
            model_info=resolved_model.model_info,
            plugin_name=resolved_model.plugin_name,
            routing_key=universal_id_to_try,
            from_queue=False,
        ),
    )
    return decisions
