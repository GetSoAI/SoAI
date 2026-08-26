"""SoAI - Dispatch-candidate routing and fast-path checks [backend/orchestrator/scheduling/dispatch_candidate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.logging.protocols import TraceLogger
from core.metrics.keyspace_base import (
    DIRECTOR_REQUESTS_EXPRESS_PATH,
    DIRECTOR_REQUESTS_FAST_PATH,
)
from core.models.provider_backing import is_provider_backed_model
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
    SchedulerWorkItem,
)
from core.tasks.task import Task
from core.types.json import JSONDict
from orchestrator.scheduling.dispatch_runtime_invariant import (
    ensure_dispatch_runtime_instance,
)
from orchestrator.scheduling.internal_protocols import (
    MetricsProtocol,
    PluginStateProtocol,
)
from orchestrator.scheduling.plugin_action_failure import (
    PluginActionFailure,
    build_prohibitive_state_failure,
)
from orchestrator.scheduling.plugin_readiness_gates import resolve_plugin_readiness_gate
from orchestrator.scheduling.provider_backed_readiness import (
    get_provider_aware_blocking_states,
    get_provider_aware_ready_states,
)

if TYPE_CHECKING:
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import AuthoritativePluginStateTransitionReceipt
    from core.state.state_names import PluginRuntimeStateName

__all__ = (
    "build_metrics_increment_express",
    "build_metrics_increment_fast",
    "handle_dispatch_candidate",
)


async def handle_dispatch_candidate(
    *,
    logger: TraceLogger,
    task: Task,
    model_info: JSONDict,
    plugin_name: str,
    routing_key: str,
    from_queue: bool,
    queue_scheduler_work: Callable[[SchedulerWorkItem], Awaitable[None]],
    schedule_plugin_dispatch: Callable[[Task, str], Awaitable[None]],
    dispatch_ready_states: set[str],
    dispatch_prohibitive_states: set[str],
    queue_mark_pending: Callable[[Task, str], Awaitable[None]],
    fail_task: Callable[[Task, PluginActionFailure], Awaitable[None]],
    is_circuit_breaker_open: Callable[[str], Awaitable[bool]],
    allow_circuit_breaker_request: Callable[[str], Awaitable[bool]],
    get_plugin_status: Callable[[str], Awaitable[PluginRuntimeStateName]],
    plugin_manager: PluginManagerProtocol,
    lifecycle_publisher: Callable[
        [str, PluginRuntimeStateName, str],
        Awaitable[AuthoritativePluginStateTransitionReceipt | None],
    ],
    get_plugin_state: Callable[[str], Awaitable[PluginStateProtocol | None]],
    reload_params_match: Callable[[str, JSONDict | None, JSONDict], Awaitable[bool]],
    get_context_startup_params: Callable[[Task], JSONDict],
    metrics_increment_express: Callable[[], None] | None,
    metrics_increment_fast: Callable[[], None] | None,
) -> None:
    context_startup_params = get_context_startup_params(task)
    provider_backed = is_provider_backed_model(model_info)
    if not provider_backed and await is_circuit_breaker_open(plugin_name):
        logger.warning(
            "Circuit breaker OPEN for plugin '%s'. Deferring task [%s].",
            plugin_name,
            task.task_id,
        )
        await _defer_dispatch_candidate(
            task=task,
            routing_key=routing_key,
            queue_mark_pending=queue_mark_pending,
            queue_scheduler_work=queue_scheduler_work,
        )
        return
    readiness_gate = await resolve_plugin_readiness_gate(
        plugin_name=plugin_name,
        get_plugin_status=get_plugin_status,
        ready_states=get_provider_aware_ready_states(dispatch_ready_states, provider_backed),
        unavailable_states=get_provider_aware_blocking_states(
            dispatch_prohibitive_states,
            provider_backed,
        ),
    )
    plugin_status = readiness_gate.plugin_status
    readiness = readiness_gate.readiness
    if readiness.unavailable:
        await fail_task(
            task,
            build_prohibitive_state_failure(plugin_name, plugin_status),
        )
        return
    if readiness.ready:
        if provider_backed:
            await schedule_plugin_dispatch(task, plugin_name)
            if (not from_queue) and metrics_increment_express is not None:
                metrics_increment_express()
            return
        runtime_guard = await ensure_dispatch_runtime_instance(
            plugin_name=plugin_name,
            provider_backed=False,
            plugin_manager=plugin_manager,
            state_aggregator_get_status=get_plugin_status,
            lifecycle_publish_state_change=lifecycle_publisher,
            dispatch_ready_states=dispatch_ready_states,
            logger=logger,
        )
        if runtime_guard.outcome == "state_changed":
            await _defer_dispatch_candidate(
                task=task,
                routing_key=routing_key,
                queue_mark_pending=queue_mark_pending,
                queue_scheduler_work=queue_scheduler_work,
            )
            return
        if runtime_guard.failure is not None:
            await fail_task(task, runtime_guard.failure)
            return
        plugin_instance = runtime_guard.plugin_instance
        is_persistent = bool(plugin_instance and plugin_instance.PERSISTENT)
        if is_persistent:
            if not await allow_circuit_breaker_request(plugin_name):
                logger.warning(
                    "Circuit breaker HALF-OPEN for plugin '%s'. Deferring task [%s].",
                    plugin_name,
                    task.task_id,
                )
                await _defer_dispatch_candidate(
                    task=task,
                    routing_key=routing_key,
                    queue_mark_pending=queue_mark_pending,
                    queue_scheduler_work=queue_scheduler_work,
                )
                return
            await schedule_plugin_dispatch(task, plugin_name)
            if (not from_queue) and metrics_increment_express is not None:
                metrics_increment_express()
            return
    state = await get_plugin_state(plugin_name)
    loaded_model_id = None
    loaded_params = None
    if state is not None:
        loaded_model_id = state.loaded_model_universal_id
        loaded_params = state.loaded_parameters
    if readiness.ready and state and loaded_model_id == routing_key:
        if await reload_params_match(plugin_name, loaded_params, context_startup_params):
            if not await allow_circuit_breaker_request(plugin_name):
                logger.warning(
                    "Circuit breaker HALF-OPEN for plugin '%s'. Deferring task [%s].",
                    plugin_name,
                    task.task_id,
                )
                await _defer_dispatch_candidate(
                    task=task,
                    routing_key=routing_key,
                    queue_mark_pending=queue_mark_pending,
                    queue_scheduler_work=queue_scheduler_work,
                )
                return
            await schedule_plugin_dispatch(task, plugin_name)
            if (not from_queue) and metrics_increment_fast is not None:
                metrics_increment_fast()
            return
    model_display_name = model_info.get("model_name") or routing_key
    logger.debug(
        "Queueing task %s for plugin %s (model=%s).",
        task.task_id,
        plugin_name,
        model_display_name,
    )
    await _defer_dispatch_candidate(
        task=task,
        routing_key=routing_key,
        queue_mark_pending=queue_mark_pending,
        queue_scheduler_work=queue_scheduler_work,
    )


async def _defer_dispatch_candidate(
    *,
    task: Task,
    routing_key: str,
    queue_mark_pending: Callable[[Task, str], Awaitable[None]],
    queue_scheduler_work: Callable[[SchedulerWorkItem], Awaitable[None]],
) -> None:
    await queue_mark_pending(task, routing_key)
    await queue_scheduler_work(
        SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY, routing_key),
    )


def build_metrics_increment_express(metrics: MetricsProtocol | None) -> Callable[[], None] | None:
    if metrics is None:
        return None

    def increment() -> None:
        metrics.increment_counter(*DIRECTOR_REQUESTS_EXPRESS_PATH)

    return increment


def build_metrics_increment_fast(metrics: MetricsProtocol | None) -> Callable[[], None] | None:
    if metrics is None:
        return None

    def increment() -> None:
        metrics.increment_counter(*DIRECTOR_REQUESTS_FAST_PATH)

    return increment
