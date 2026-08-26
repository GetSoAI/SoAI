"""SoAI - Virtual model resolution for scheduler [backend/orchestrator/scheduling/virtual_model_evaluation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.events.bus_dispatch_logging import resolve_event_trace_id
from core.logging.trace import get_logger
from core.orchestrator.execution_plan import (
    DEFAULT_NO_VIRTUAL_MODELS_REASON,
    EXECUTION_PLAN_STATUS_AVAILABLE,
    EXECUTION_PLAN_STATUS_ON_COOLDOWN,
    ExecutionPlan,
    resolve_execution_plan_failure_reason,
)
from core.orchestrator.routing_config import VirtualModelConfig
from core.tasks.errors import TASK_STATE_PERSISTENCE_FAILED_MESSAGE
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.orchestration_persistence import cache_and_persist_orchestration_state
from core.tasks.task import Task
from orchestrator.queueing.execution_plan_context import (
    apply_execution_plan_context,
)
from orchestrator.queueing.execution_plan_error_handling import (
    run_execution_plan_with_reservation_guard,
)
from orchestrator.scheduling.action_generation_dependencies import (
    SchedulerActionGenerationDependencies,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "VirtualModelResolutionResult",
    "evaluate_virtual_model_routing",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.virtual_model_evaluation"
OPERATION_HANDLE_AVAILABLE_PLAN = "orchestrator.scheduler.virtual_model.available_plan"


@dataclass(frozen=True, slots=True)
class VirtualModelResolutionResult:
    status: Literal["resolved", "on_cooldown", "unavailable", "not_virtual"]
    task: Task
    context: OrchestrationContext
    universal_id: str | None
    pending_key: str
    moved: bool
    model_info: JSONDict | None = None
    plugin_name: str | None = None
    failure_reason: str | None = None


async def evaluate_virtual_model_routing(
    deps: SchedulerActionGenerationDependencies,
    task: Task,
    context: OrchestrationContext,
    routing_key: str,
    virtual_model_map: dict[str, VirtualModelConfig],
) -> VirtualModelResolutionResult:
    if routing_key not in virtual_model_map:
        return VirtualModelResolutionResult(
            status="not_virtual",
            task=task,
            context=context,
            universal_id=routing_key,
            pending_key=routing_key,
            moved=False,
        )
    if context.event is None:
        return VirtualModelResolutionResult(
            status="unavailable",
            task=task,
            context=context,
            universal_id=None,
            pending_key=routing_key,
            moved=False,
            failure_reason="No event available for virtual model resolution.",
        )
    plan = await deps.resolve_execution_plan(
        task,
        context,
        set(context.excluded_universal_ids) if context.excluded_universal_ids else None,
    )
    if plan["status"] == EXECUTION_PLAN_STATUS_AVAILABLE:
        return await run_execution_plan_with_reservation_guard(
            reservations=deps.queue.execution_reservations,
            tracking_id=context.tracking_id,
            awaitable=_handle_available_plan(deps, task, context, routing_key, plan),
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION_HANDLE_AVAILABLE_PLAN,
            message="Failed to handle available virtual model plan.",
            details={"tracking_id": context.tracking_id, "routing_key": routing_key},
        )
    if plan["status"] == EXECUTION_PLAN_STATUS_ON_COOLDOWN:
        await deps.queue.tracking.set_deferral_reason(
            routing_key,
            "Virtual model backends are on cooldown.",
        )
        return VirtualModelResolutionResult(
            status="on_cooldown",
            task=task,
            context=context,
            universal_id=None,
            pending_key=routing_key,
            moved=False,
        )
    resolved_failure_reason = resolve_execution_plan_failure_reason(
        plan,
        default_reason=DEFAULT_NO_VIRTUAL_MODELS_REASON,
    )
    return VirtualModelResolutionResult(
        status="unavailable",
        task=task,
        context=context,
        universal_id=None,
        pending_key=routing_key,
        moved=False,
        failure_reason=resolved_failure_reason,
    )


async def _handle_available_plan(
    deps: SchedulerActionGenerationDependencies,
    task: Task,
    context: OrchestrationContext,
    routing_key: str,
    plan: ExecutionPlan,
) -> VirtualModelResolutionResult:
    logger = get_logger(LOGGER_NAME)
    logger.debug(
        "Virtual model '%s' is now available. Updating task [%s] with new plan.",
        routing_key,
        task.task_id,
    )
    plan_context = await apply_execution_plan_context(
        queue=deps.queue,
        task=task,
        context=context,
        plan=plan,
        routing_key=(
            plan["universal_ids_to_try"][0] if plan["universal_ids_to_try"] else routing_key
        ),
    )
    updated_task = plan_context.task
    updated_context = plan_context.context
    resolved_model = plan_context.resolved_model
    if updated_context.execution_universal_ids and resolved_model is None:
        primary_universal_id = updated_context.execution_universal_ids[0]
        await deps.queue.execution_reservations.release(updated_context.tracking_id)
        return VirtualModelResolutionResult(
            status="unavailable",
            task=updated_task,
            context=updated_context,
            universal_id=None,
            pending_key=routing_key,
            moved=False,
            failure_reason=plan_context.error_reason
            or f"Model info for {primary_universal_id} is invalid.",
        )
    persisted, _ = await cache_and_persist_orchestration_state(
        deps.task_registry,
        updated_task,
        logger=logger,
        operation="orchestrator.scheduler.virtual_model.persist_context",
        trace_id=resolve_event_trace_id(updated_context.event),
    )
    if not persisted:
        await deps.queue.execution_reservations.release(updated_context.tracking_id)
        return VirtualModelResolutionResult(
            status="unavailable",
            task=updated_task,
            context=updated_context,
            universal_id=None,
            pending_key=routing_key,
            moved=False,
            failure_reason=TASK_STATE_PERSISTENCE_FAILED_MESSAGE,
        )
    if not updated_context.execution_universal_ids:
        await deps.queue.execution_reservations.release(updated_context.tracking_id)
        return VirtualModelResolutionResult(
            status="unavailable",
            task=updated_task,
            context=updated_context,
            universal_id=None,
            pending_key=routing_key,
            moved=False,
            failure_reason=DEFAULT_NO_VIRTUAL_MODELS_REASON,
        )
    universal_id = updated_context.execution_universal_ids[0]
    moved = False
    pending_key = routing_key
    if universal_id:
        moved = await deps.queue.tracking.move_pending_task(
            updated_task,
            routing_key,
            universal_id,
            insert_left=True,
        )
        if moved:
            pending_key = universal_id
    return VirtualModelResolutionResult(
        status="resolved",
        task=updated_task,
        context=updated_context,
        universal_id=universal_id,
        pending_key=pending_key,
        moved=moved,
        model_info=resolved_model.model_info if resolved_model is not None else None,
        plugin_name=resolved_model.plugin_name if resolved_model is not None else None,
    )
