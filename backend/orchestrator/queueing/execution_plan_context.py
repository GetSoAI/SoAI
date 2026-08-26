"""SoAI - Execution plan context application [backend/orchestrator/queueing/execution_plan_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from orchestrator.model_info_resolution import (
    ResolvedOrchestratorModel,
    resolve_orchestrator_model,
)
from orchestrator.queueing.parameter_snapshot import (
    apply_parameter_snapshot_state_to_context,
    copy_parameter_overrides,
)

if TYPE_CHECKING:
    from core.orchestrator.execution_plan import ExecutionPlan
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = (
    "ExecutionPlanContextResult",
    "apply_execution_plan_context",
    "apply_execution_plan_fields",
    "apply_primary_model_context",
    "build_available_execution_plan_context",
    "resolve_execution_plan_routing_key",
)


@dataclass(frozen=True, slots=True)
class ExecutionPlanContextResult:
    task: Task
    context: OrchestrationContext
    resolved_model: ResolvedOrchestratorModel | None
    error_reason: str | None


def resolve_execution_plan_routing_key(
    context: OrchestrationContext,
    plan: ExecutionPlan,
    *,
    requested_model_name: str,
) -> str | None:
    if plan["universal_ids_to_try"]:
        return plan["universal_ids_to_try"][0]
    virtual_model_name = plan.get("virtual_model_name")
    if isinstance(virtual_model_name, str) and virtual_model_name:
        return virtual_model_name
    deferral_key = plan.get("deferral_key")
    if isinstance(deferral_key, str) and deferral_key:
        return deferral_key
    if requested_model_name:
        return requested_model_name
    return context.routing_key


def apply_execution_plan_fields(
    context: OrchestrationContext,
    plan: ExecutionPlan,
    *,
    routing_key: str | None,
) -> OrchestrationContext:
    return replace(
        context,
        execution_universal_ids=tuple(plan["universal_ids_to_try"]),
        parameter_overrides=copy_parameter_overrides(plan["parameter_overrides"]),
        virtual_model_name=plan["virtual_model_name"],
        routing_key=routing_key,
    )


async def apply_primary_model_context(
    queue: OrchestratorQueueProtocol,
    task: Task,
    context: OrchestrationContext,
    resolved_model: ResolvedOrchestratorModel,
) -> tuple[Task, OrchestrationContext]:
    updated_context = replace(
        context,
        routing_key=resolved_model.universal_id,
        plugin_name=resolved_model.plugin_name,
    )
    updated_task = task.with_orchestration_context(updated_context)
    updated_context = await apply_parameter_snapshot_state_to_context(
        queue=queue,
        task=updated_task,
        context=updated_context,
        plugin_name=resolved_model.plugin_name,
    )
    updated_task = updated_task.with_orchestration_context(updated_context)
    return (updated_task, updated_context)


async def build_available_execution_plan_context(
    queue: QueueServiceView,
    task: Task,
    plan: ExecutionPlan,
) -> ExecutionPlanContextResult:
    return await apply_execution_plan_context(
        queue=queue,
        task=task,
        context=task.require_orchestration_context(),
        plan=plan,
        routing_key=plan["universal_ids_to_try"][0] if plan["universal_ids_to_try"] else None,
    )


async def apply_execution_plan_context(
    *,
    queue: OrchestratorQueueProtocol,
    task: Task,
    context: OrchestrationContext,
    plan: ExecutionPlan,
    routing_key: str | None,
) -> ExecutionPlanContextResult:
    context = apply_execution_plan_fields(
        context,
        plan,
        routing_key=routing_key,
    )
    task = task.with_orchestration_context(context)
    if not context.execution_universal_ids:
        return ExecutionPlanContextResult(
            task=task,
            context=context,
            resolved_model=None,
            error_reason=None,
        )
    universal_id = context.execution_universal_ids[0]
    resolved_model, error_reason = await resolve_orchestrator_model(
        queue.orchestrator_deps.model_information_service,
        universal_id=universal_id,
        require_canonical_universal_id=False,
    )
    if resolved_model is None:
        return ExecutionPlanContextResult(
            task=task,
            context=context,
            resolved_model=None,
            error_reason=error_reason or f"Model info for {universal_id} is invalid.",
        )
    task, context = await apply_primary_model_context(queue, task, context, resolved_model)
    return ExecutionPlanContextResult(
        task=task,
        context=context,
        resolved_model=resolved_model,
        error_reason=None,
    )
