"""SoAI - Scheduler dispatch candidate orchestration [backend/orchestrator/scheduling/dispatch_candidate_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.state.state_transition_sets import (
    DISPATCH_READY_STATES,
    UNAVAILABLE_PLUGIN_STATES,
)
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.types.json import JSONDict
from orchestrator.scheduling.dependencies import SchedulerDispatchCandidateDependencies
from orchestrator.scheduling.dispatch_candidate import (
    build_metrics_increment_express,
    build_metrics_increment_fast,
    handle_dispatch_candidate,
)
from orchestrator.scheduling.plugin_action_failure import PluginActionFailure

__all__ = ("handle_scheduler_dispatch_candidate",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.dispatch_candidate_handler"


async def handle_scheduler_dispatch_candidate(
    *,
    deps: SchedulerDispatchCandidateDependencies,
    task: Task,
    model_info: JSONDict,
    plugin_name: str,
    routing_key: str,
    from_queue: bool = False,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if task.status == TaskStatus.DEDUPED:
        logger.debug("Skipping dispatch candidate for deduped task %s.", task.task_id)
        return

    async def queue_mark_pending(queued_task: Task, key: str) -> None:
        await deps.queue.mark_task_pending(queued_task, key, plugin_name=plugin_name)

    async def fail_task(queued_task: Task, failure: PluginActionFailure) -> None:
        await deps.outcomes.fail_task(
            queued_task,
            failure.message,
            allow_failover=True,
            error_type=failure.error_type,
        )

    def get_context_startup_params(queued_task: Task) -> JSONDict:
        return dict(deps.queue.require_orchestration_context(queued_task).startup_params)

    await handle_dispatch_candidate(
        logger=logger,
        task=task,
        model_info=model_info,
        plugin_name=plugin_name,
        routing_key=routing_key,
        from_queue=from_queue,
        queue_scheduler_work=deps.queue_scheduler_work,
        schedule_plugin_dispatch=deps.schedule_plugin_dispatch,
        dispatch_ready_states=set(DISPATCH_READY_STATES),
        dispatch_prohibitive_states=set(UNAVAILABLE_PLUGIN_STATES),
        queue_mark_pending=queue_mark_pending,
        fail_task=fail_task,
        is_circuit_breaker_open=deps.lifecycle.circuit_breakers.is_circuit_breaker_open,
        allow_circuit_breaker_request=(
            deps.lifecycle.circuit_breakers.allow_circuit_breaker_request
        ),
        get_plugin_status=deps.orchestrator.state_aggregator.get_plugin_status,
        plugin_manager=deps.orchestrator.plugin_manager,
        lifecycle_publisher=deps.lifecycle.publisher.publish_runtime_state_change,
        get_plugin_state=deps.lifecycle.watchers.get_plugin_state,
        reload_params_match=deps.lifecycle.task_tracking.reload_params_match,
        get_context_startup_params=get_context_startup_params,
        metrics_increment_express=build_metrics_increment_express(deps.orchestrator.metrics),
        metrics_increment_fast=build_metrics_increment_fast(deps.orchestrator.metrics),
    )
