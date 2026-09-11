"""SoAI - Model waiter dispatching and rollback handling [backend/orchestrator/scheduling/waiter_dispatching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger
from core.models.provider_backing import is_provider_backed_model
from core.orchestrator.protocols_queue import QueueTrackingViewProtocol
from core.state.state_names import (
    ORCH_STATE_READY,
    ORCH_STATE_READY_PENDING_DISPATCH,
    PLUGIN_STATE_PERSISTENT_READY,
)
from core.state.state_transition_sets import UNAVAILABLE_PLUGIN_STATES
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from core.timing.constants import INTERACTIVE_TIMEOUT_SEC
from core.types.json import JSONDict
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.scheduling.dispatch_runtime_invariant import (
    ensure_scheduler_dispatch_runtime_instance,
)
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.plugin_readiness_gates import (
    resolve_deferred_warning_suffix,
    resolve_plugin_readiness_gate,
)
from orchestrator.scheduling.plugin_warning_throttles import (
    get_plugin_warning_throttle,
)
from orchestrator.scheduling.provider_backed_readiness import (
    get_provider_aware_blocking_states,
    get_provider_aware_ready_states,
)
from orchestrator.scheduling.waiter_pending_restoration import (
    restore_unscheduled_waiters,
)

__all__ = ("dispatch_waiters_for_ready_model",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.waiter_dispatching"
OPERATION = "orchestrator.scheduler.dispatch_waiters"


async def dispatch_waiters_for_ready_model(
    *,
    deps: SchedulerDispatchingDependencies,
    dispatch_waiters_not_ready_warners: dict[str, RateLimitedLogger],
    pending_key: str,
    plugin_name: str,
    model_info: JSONDict,
) -> None:
    logger = get_logger(LOGGER_NAME)
    universal_id_value = model_info.get("universal_id", pending_key)
    universal_id = (
        universal_id_value
        if isinstance(universal_id_value, str) and universal_id_value
        else pending_key
    )
    provider_backed = is_provider_backed_model(model_info)
    readiness_gate = await resolve_plugin_readiness_gate(
        plugin_name=plugin_name,
        get_plugin_status=deps.state_aggregator.get_plugin_status,
        ready_states=get_provider_aware_ready_states(deps.dispatch_ready_states, provider_backed),
        unavailable_states=get_provider_aware_blocking_states(
            UNAVAILABLE_PLUGIN_STATES,
            provider_backed,
        ),
    )
    plugin_status = readiness_gate.plugin_status
    readiness = readiness_gate.readiness
    if not readiness.ready:
        warner = get_plugin_warning_throttle(
            dispatch_waiters_not_ready_warners,
            plugin_name,
            interval_seconds=INTERACTIVE_TIMEOUT_SEC,
        )
        suffix = resolve_deferred_warning_suffix(warner)
        if suffix is not None:
            logger.warning(
                "Skipping waiter dispatch for model [%s] on plugin '%s' because plugin state is '%s'.%s",
                universal_id,
                plugin_name,
                plugin_status,
                suffix,
            )
        await _record_waiter_deferral_reason(
            deps.queue.tracking,
            pending_key,
            universal_id,
            f"Plugin '{plugin_name}' is not execution-ready (state: {plugin_status}).",
        )
        return
    runtime_guard = await ensure_scheduler_dispatch_runtime_instance(
        deps=deps,
        plugin_name=plugin_name,
        provider_backed=provider_backed,
        logger=logger,
    )
    if runtime_guard.outcome == "state_changed":
        await _record_waiter_deferral_reason(
            deps.queue.tracking,
            pending_key,
            universal_id,
            f"Plugin '{plugin_name}' changed state before waiter dispatch.",
        )
        return
    if runtime_guard.failure is not None:
        await _record_waiter_deferral_reason(
            deps.queue.tracking,
            pending_key,
            universal_id,
            runtime_guard.failure.message,
        )
        return
    plugin_instance = runtime_guard.plugin_instance
    persistent_plugin = bool(plugin_instance and plugin_instance.PERSISTENT)
    state = await deps.lifecycle.watchers.get_plugin_state(plugin_name)
    if state is not None and not provider_backed and not persistent_plugin:
        loaded_uid = state.loaded_model_universal_id
        if isinstance(loaded_uid, str) and loaded_uid and loaded_uid != universal_id:
            await _record_waiter_deferral_reason(
                deps.queue.tracking,
                pending_key,
                universal_id,
                f"Plugin '{plugin_name}' has a different model loaded ({loaded_uid}); waiting for '{universal_id}'.",
            )
            return
    unregistered_key = pending_key
    waiters = list(await deps.queue.tracking.unregister_pending_queue(pending_key))
    if not waiters and pending_key != universal_id:
        unregistered_key = universal_id
        waiters = list(await deps.queue.tracking.unregister_pending_queue(universal_id))
    if not waiters:
        await _settle_ready_pending_dispatch(
            deps=deps,
            plugin_name=plugin_name,
            universal_id=universal_id,
            persistent_plugin=persistent_plugin,
        )
        return
    tasks_to_process = [waiter for waiter in waiters if waiter.status != TaskStatus.CANCELLED]
    if not tasks_to_process:
        await _settle_ready_pending_dispatch(
            deps=deps,
            plugin_name=plugin_name,
            universal_id=universal_id,
            persistent_plugin=persistent_plugin,
        )
        return
    loaded_parameters = state.loaded_parameters if state is not None else None
    compatible_waiters: list[Task] = []
    scheduled_task_ids: set[str] = set()
    try:
        for task in tasks_to_process:
            context = task.require_orchestration_context()
            compatible = (
                persistent_plugin
                or await deps.lifecycle.task_tracking.reload_params_match(
                    plugin_name,
                    loaded_parameters,
                    dict(context.startup_params),
                )
            )
            if compatible:
                compatible_waiters.append(task)
        if compatible_waiters:
            logger.info(
                "Model [%s] is ready. Dispatching %s compatible waiting tasks to plugin queue.",
                universal_id,
                len(compatible_waiters),
            )
        for task in compatible_waiters:
            await deps.schedule_plugin_dispatch(task, plugin_name)
            scheduled_task_ids.add(task.task_id)
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="orchestrator.scheduler.dispatch_waiters",
        )
        log_exception(
            logger,
            coerced,
            message="Model waiter dispatch failed; restoring pending tasks.",
            operation=OPERATION,
            details={"plugin": plugin_name, "routing_key": unregistered_key},
            level="warning",
        )
        raise
    finally:
        unscheduled_waiters = [
            task for task in tasks_to_process if task.task_id not in scheduled_task_ids
        ]
        if unscheduled_waiters:
            await uncancel_then_cleanup(
                restore_unscheduled_waiters(
                    tracking=deps.queue.tracking,
                    tasks_to_process=unscheduled_waiters,
                    scheduled_count=0,
                    pending_key=unregistered_key,
                    plugin_name=plugin_name,
                ),
            )
        if not scheduled_task_ids:
            await uncancel_then_cleanup(
                _settle_ready_pending_dispatch(
                    deps=deps,
                    plugin_name=plugin_name,
                    universal_id=universal_id,
                    persistent_plugin=persistent_plugin,
                ),
            )


async def _settle_ready_pending_dispatch(
    *,
    deps: SchedulerDispatchingDependencies,
    plugin_name: str,
    universal_id: str,
    persistent_plugin: bool,
) -> None:
    current_status = await deps.state_aggregator.get_plugin_status(plugin_name)
    if current_status != ORCH_STATE_READY_PENDING_DISPATCH:
        return
    state = await deps.lifecycle.watchers.get_plugin_state(plugin_name)
    if state is None or state.loaded_model_universal_id != universal_id:
        return
    await publish_runtime_state_change_and_wait(
        publisher=deps.lifecycle.publisher,
        plugin_name=plugin_name,
        new_state=(PLUGIN_STATE_PERSISTENT_READY if persistent_plugin else ORCH_STATE_READY),
        reason="Model load handoff completed without a compatible waiter.",
        details={"universal_id": universal_id},
        expected_previous_state=ORCH_STATE_READY_PENDING_DISPATCH,
    )


async def _record_waiter_deferral_reason(
    tracking: QueueTrackingViewProtocol,
    pending_key: str,
    universal_id: str,
    reason: str,
) -> None:
    await tracking.set_deferral_reason(pending_key, reason)
    if pending_key != universal_id:
        await tracking.set_deferral_reason(universal_id, reason)
