"""SoAI - Scheduler dispatch admission and purge gating [backend/orchestrator/scheduling/dispatching_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable

from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.state.state_transition_sets import SCHEDULER_UNAVAILABLE_PLUGIN_STATES
from core.tasks.task import Task
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from orchestrator.scheduling.dispatch_rejections import (
    fail_released_dispatch_task,
)
from orchestrator.scheduling.dispatch_runtime_invariant import (
    ensure_scheduler_dispatch_runtime_instance,
)
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.dispatching_queue_handoff import (
    admit_dispatch_queue_handoff,
)
from orchestrator.scheduling.plugin_action_failure import (
    build_prohibitive_state_failure,
)
from orchestrator.scheduling.plugin_dispatch_readiness import (
    requeue_deferred_plugin_dispatch,
)
from orchestrator.scheduling.plugin_queue_dispatcher import PluginQueueDispatcherLoop
from orchestrator.scheduling.plugin_warning_throttles import (
    get_plugin_warning_throttle,
)
from orchestrator.scheduling.provider_backed_readiness import (
    resolve_provider_aware_plugin_readiness_state_for_dispatch,
    task_targets_provider_backed_model,
)
from orchestrator.scheduling.purge_state import SchedulerPurgeState

__all__ = ("dispatch_task_to_plugin_queue",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.dispatching_admission"


async def dispatch_task_to_plugin_queue(
    *,
    deps: SchedulerDispatchingDependencies,
    plugin_queue_dispatcher_loop: PluginQueueDispatcherLoop,
    dispatch_not_ready_warners: dict[str, RateLimitedLogger],
    dispatcher_lock: asyncio.Lock,
    plugin_queue_dispatchers: dict[str, asyncio.Task[None]],
    purge_state: SchedulerPurgeState,
    cleanup_plugin_queue_dispatcher: Callable[[str, asyncio.Task[None]], None],
    task: Task,
    plugin_name: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    task, cancel_decision = await deps.queue.ensure_prompt_slot_and_cancel_if_cancelled(task)
    if cancel_decision:
        decision_reason = cancel_decision.reason
        await deps.outcomes.cancel_task(task, decision_reason or "Task cancelled before dispatch.")
        return
    current_plugin_status, readiness = (
        await resolve_provider_aware_plugin_readiness_state_for_dispatch(
            plugin_name=plugin_name,
            deps=deps,
            unavailable_states=SCHEDULER_UNAVAILABLE_PLUGIN_STATES,
            task=task,
        )
    )
    if readiness.unavailable:
        failure = build_prohibitive_state_failure(plugin_name, current_plugin_status)
        await fail_released_dispatch_task(
            deps,
            task,
            failure.message,
            allow_failover=True,
            error_type=failure.error_type,
        )
        return
    if readiness.deferred:
        context = task.orchestration_context
        if context is None:
            await fail_released_dispatch_task(
                deps,
                task,
                "Task missing orchestration context; cannot requeue for scheduler.",
                allow_failover=False,
            )
            return
        warner = get_plugin_warning_throttle(
            dispatch_not_ready_warners,
            plugin_name,
            interval_seconds=INTERACTIVE_TIMEOUT_SEC,
        )
        await requeue_deferred_plugin_dispatch(
            queue=deps.queue,
            task_registry=deps.task_registry,
            outcomes=deps.outcomes,
            task=task,
            logger=logger,
            operation="orchestrator.dispatch_task_to_plugin_queue.requeue_not_ready",
            warning_message=(
                "Deferring dispatch of task [%s] for plugin '%s' because plugin state is '%s'. "
                "Re-queuing for scheduler.%s"
            ),
            warning_args=(task.task_id, plugin_name, current_plugin_status),
            warner=warner,
        )
        return
    provider_backed = await task_targets_provider_backed_model(
        deps.model_information_service,
        task,
    )
    runtime_guard = await ensure_scheduler_dispatch_runtime_instance(
        deps=deps,
        plugin_name=plugin_name,
        provider_backed=provider_backed,
        logger=logger,
    )
    if runtime_guard.outcome == "state_changed":
        state_changed_warning = (
            "Deferring dispatch of task [%s] for plugin '%s' because runtime state changed. "
            "Re-queuing for scheduler."
        )
        await requeue_deferred_plugin_dispatch(
            queue=deps.queue,
            task_registry=deps.task_registry,
            outcomes=deps.outcomes,
            task=task,
            logger=logger,
            operation="orchestrator.dispatch_task_to_plugin_queue.requeue_runtime_state_changed",
            warning_message=state_changed_warning,
            warning_args=(task.task_id, plugin_name),
            warner=None,
        )
        return
    if runtime_guard.failure is not None:
        await fail_released_dispatch_task(
            deps,
            task,
            runtime_guard.failure.message,
            allow_failover=True,
            error_type=runtime_guard.failure.error_type,
        )
        return
    await admit_dispatch_queue_handoff(
        deps=deps,
        plugin_queue_dispatcher_loop=plugin_queue_dispatcher_loop,
        dispatcher_lock=dispatcher_lock,
        plugin_queue_dispatchers=plugin_queue_dispatchers,
        purge_state=purge_state,
        cleanup_plugin_queue_dispatcher=cleanup_plugin_queue_dispatcher,
        task=task,
        plugin_name=plugin_name,
        logger=logger,
    )
