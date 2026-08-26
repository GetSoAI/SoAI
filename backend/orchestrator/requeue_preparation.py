"""SoAI - Orchestrator requeue context preparation [backend/orchestrator/requeue_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass, replace

from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task

__all__ = (
    "REQUEUE_BLOCKED_BY_DELIVERY_MESSAGE",
    "RequeueAttemptResult",
    "is_requeue_blocked_by_delivery",
    "prepare_task_for_requeue",
)

REQUEUE_BLOCKED_BY_DELIVERY_MESSAGE = "Cannot requeue task after delivery started."


@dataclass(frozen=True, slots=True)
class RequeueAttemptResult:
    task: Task
    requeued: bool
    blocked_by_delivery: bool


def is_requeue_blocked_by_delivery(context: OrchestrationContext) -> bool:
    return bool(context.delivery_in_progress or context.streaming_started)


def prepare_task_for_requeue(
    task: Task,
    *,
    clear_parameter_snapshot: bool = False,
) -> Task:
    context = task.require_orchestration_context()
    if is_requeue_blocked_by_delivery(context):
        return task
    if clear_parameter_snapshot:
        next_routing_key = (
            context.execution_universal_ids[0]
            if context.execution_universal_ids
            else context.routing_key
        )
        context = replace(
            context,
            parameter_snapshot=None,
            startup_params={},
            inference_params={},
            parameter_version=None,
            startup_param_fingerprint=None,
            plugin_name=None,
            routing_key=next_routing_key,
        )
    context = replace(context, is_requeued=True)
    context = context.with_reset_delivery_state()
    return task.with_orchestration_context(context)
