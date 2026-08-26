"""SoAI - Deferred task orchestration context repair [backend/orchestrator/queueing/deferred_task_context_repair.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace

from core.events.bus_dispatch_logging import resolve_event_trace_id
from core.logging.protocols import TraceLogger
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.tasks.orchestration_context import (
    OrchestrationContext,
)
from core.tasks.orchestration_persistence import cache_and_persist_orchestration_state
from core.tasks.task import Task
from orchestrator.model_info_resolution import resolve_orchestrator_model
from orchestrator.queueing.execution_plan_context import (
    apply_primary_model_context,
)

__all__ = (
    "DeferredTaskContextRepairResult",
    "try_repair_deferred_task_context",
)


@dataclass(frozen=True, slots=True)
class DeferredTaskContextRepairResult:
    task: Task
    context: OrchestrationContext
    persisted: bool
    plugin_matches: bool


async def try_repair_deferred_task_context(
    queue: OrchestratorQueueProtocol,
    task: Task,
    context: OrchestrationContext,
    *,
    deferral_key: str,
    logger: TraceLogger,
    operation: str,
    expected_plugin_name: str | None = None,
) -> DeferredTaskContextRepairResult:
    resolved_model, _ = await resolve_orchestrator_model(
        queue.orchestrator_deps.model_information_service,
        deferral_key,
        require_canonical_universal_id=False,
    )
    if resolved_model is None:
        return DeferredTaskContextRepairResult(
            task=task,
            context=context,
            persisted=False,
            plugin_matches=False,
        )
    if expected_plugin_name is not None and resolved_model.plugin_name != expected_plugin_name:
        return DeferredTaskContextRepairResult(
            task=task,
            context=context,
            persisted=False,
            plugin_matches=False,
        )
    updated_context = replace(
        context,
        execution_universal_ids=(resolved_model.universal_id,),
    )
    updated_task = task.with_orchestration_context(updated_context)
    updated_task, updated_context = await apply_primary_model_context(
        queue,
        updated_task,
        updated_context,
        resolved_model,
    )
    persisted, _ = await cache_and_persist_orchestration_state(
        queue.task_registry,
        updated_task,
        logger=logger,
        operation=operation,
        trace_id=resolve_event_trace_id(updated_context.event),
    )
    if not persisted:
        await queue.tracking.set_deferral_reason(
            deferral_key,
            "Could not persist repaired orchestration context while deferring task.",
        )
    return DeferredTaskContextRepairResult(
        task=updated_task,
        context=updated_context,
        persisted=bool(persisted),
        plugin_matches=True,
    )
