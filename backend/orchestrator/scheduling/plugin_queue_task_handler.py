"""SoAI - Single-task dispatch decision for plugin queues [backend/orchestrator/scheduling/plugin_queue_task_handler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.models.provider_backing import is_provider_backed_model
from core.orchestrator.protocols_queue import QueueCycleType
from core.state.state_transition_sets import SCHEDULER_UNAVAILABLE_PLUGIN_STATES
from orchestrator.model_info_resolution import resolve_orchestrator_model
from orchestrator.queueing.deferred_task_context_repair import (
    try_repair_deferred_task_context,
)
from orchestrator.requeue_attempts import (
    build_scheduler_requeue_attempt_spec,
    execute_requeue_attempt,
)
from orchestrator.scheduling.dispatch_runtime_invariant import (
    ensure_scheduler_dispatch_runtime_instance,
)
from orchestrator.scheduling.plugin_action_failure import (
    build_prohibitive_state_failure,
)
from orchestrator.scheduling.plugin_dispatch_readiness import (
    requeue_deferred_plugin_dispatch,
)
from orchestrator.scheduling.provider_backed_readiness import (
    resolve_provider_aware_plugin_readiness_state_for_dispatch,
)

if TYPE_CHECKING:
    from core.logging.rate_limited_logger import RateLimitedLogger
    from core.tasks.task import Task
    from orchestrator.scheduling.internal_protocols import (
        PluginQueueDispatcherDependenciesProtocol,
    )

__all__ = ("handle_dispatched_task",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.plugin_queue_task_handler"


async def _requeue_missing_execution_plan(
    deps: PluginQueueDispatcherDependenciesProtocol,
    task: Task,
    *,
    operation: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    await execute_requeue_attempt(
        deps.queue,
        deps.task_registry,
        task,
        spec=build_scheduler_requeue_attempt_spec(
            logger=logger,
            operation=operation,
        ),
        outcomes=deps.outcomes,
    )


async def handle_dispatched_task(
    deps: PluginQueueDispatcherDependenciesProtocol,
    plugin_name: str,
    task: Task,
    *,
    requeue_warner: RateLimitedLogger,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if await deps.queue.is_task_cancelled(task):
        cancellation_reason = await deps.cancellation_history.get_reason(task.cancellation_id)
        if cancellation_reason is None:
            cancellation_reason = "Task was cancelled (reason unavailable)."
            logger.warning(
                "Cancellation reason missing for task [%s]. Using default.",
                task.task_id,
            )
        await deps.queue.cycles.close_cycle(task, QueueCycleType.PLUGIN)
        await deps.outcomes.cancel_task(task, cancellation_reason)
        return
    unavailable_states = SCHEDULER_UNAVAILABLE_PLUGIN_STATES
    current_plugin_status, readiness = (
        await resolve_provider_aware_plugin_readiness_state_for_dispatch(
            plugin_name=plugin_name,
            deps=deps,
            unavailable_states=unavailable_states,
            task=task,
        )
    )
    if readiness.unavailable:
        failure = build_prohibitive_state_failure(plugin_name, current_plugin_status)
        failure_message = failure.message
        failure_error_type = failure.error_type
        await deps.queue.cycles.close_cycle(task, QueueCycleType.PLUGIN)
        await deps.outcomes.fail_task(
            task,
            failure_message,
            allow_failover=True,
            error_type=failure_error_type,
        )
        return
    if readiness.deferred:
        requeue_operation = "orchestrator.scheduler.plugin_queue_requeue"
        await requeue_deferred_plugin_dispatch(
            queue=deps.queue,
            task_registry=deps.task_registry,
            outcomes=deps.outcomes,
            task=task,
            logger=logger,
            operation=requeue_operation,
            warning_message="Caught request for '%s' after state changed to '%s'. Re-queuing.%s",
            warning_args=(plugin_name, current_plugin_status),
            warner=requeue_warner,
        )
        return
    context = deps.queue.require_orchestration_context(task)
    if not context.execution_universal_ids:
        logger.warning(
            "Task [%s] is missing execution universal ids in plugin queue for '%s'; attempting recovery.",
            task.task_id,
            plugin_name,
        )
        routing_key_value = context.routing_key
        routing_key = routing_key_value if isinstance(routing_key_value, str) else ""
        if not routing_key:
            await _requeue_missing_execution_plan(
                deps,
                task,
                operation="orchestrator.scheduler.plugin_queue_missing_plan.requeue",
            )
            return
        repair_result = await try_repair_deferred_task_context(
            deps.queue,
            task,
            context,
            deferral_key=routing_key,
            logger=logger,
            operation="orchestrator.scheduler.plugin_queue_missing_plan.repair",
            expected_plugin_name=plugin_name,
        )
        if not repair_result.plugin_matches:
            await _requeue_missing_execution_plan(
                deps,
                task,
                operation="orchestrator.scheduler.plugin_queue_missing_plan.requeue",
            )
            return
        task = repair_result.task
        context = repair_result.context
        if not repair_result.persisted:
            await _requeue_missing_execution_plan(
                deps,
                task,
                operation="orchestrator.scheduler.plugin_queue_missing_plan.persist_failed",
            )
            return
    universal_id = context.execution_universal_ids[0]
    resolved_model, error_reason = await resolve_orchestrator_model(
        deps.model_information_service,
        universal_id,
        require_canonical_universal_id=True,
    )
    if resolved_model is None:
        if error_reason == "Model info missing required universal_id during plugin queue dispatch.":
            raise ValidationError(
                error_reason,
                operation="orchestrator.scheduler.plugin_queue_dispatch.universal_id",
                details={"plugin_name": plugin_name},
            )
        failure_reason = (
            f"Model info for {universal_id} not found during plugin queue dispatch."
            if error_reason == f"Model info for {universal_id} not found."
            else error_reason or f"Model info for {universal_id} is invalid."
        )
        await deps.queue.cycles.close_cycle(task, QueueCycleType.PLUGIN)
        await deps.outcomes.fail_task(
            task,
            failure_reason,
            allow_failover=False,
        )
        return
    provider_backed = is_provider_backed_model(resolved_model.model_info)
    runtime_guard = await ensure_scheduler_dispatch_runtime_instance(
        deps=deps,
        plugin_name=plugin_name,
        provider_backed=provider_backed,
        logger=logger,
    )
    if runtime_guard.outcome == "state_changed":
        operation = "orchestrator.scheduler.plugin_queue_runtime_state_changed.requeue"
        warning_message = "Caught request for '%s' after runtime state changed. Re-queuing.%s"
        await requeue_deferred_plugin_dispatch(
            queue=deps.queue,
            task_registry=deps.task_registry,
            outcomes=deps.outcomes,
            task=task,
            logger=logger,
            operation=operation,
            warning_message=warning_message,
            warning_args=(plugin_name,),
            warner=requeue_warner,
        )
        return
    if runtime_guard.failure is not None:
        await deps.queue.cycles.close_cycle(task, QueueCycleType.PLUGIN)
        await deps.outcomes.fail_task(
            task,
            runtime_guard.failure.message,
            allow_failover=True,
            error_type=runtime_guard.failure.error_type,
        )
        return
    await deps.inference_executor.execute_inference_on_task(
        task,
        plugin_name,
        resolved_model.model_info,
    )
