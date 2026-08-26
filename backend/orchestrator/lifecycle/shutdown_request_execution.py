"""SoAI - Stop request execution for lifecycle shutdown [backend/orchestrator/lifecycle/shutdown_request_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.concurrency.context import create_system_cancellation_id
from core.concurrency.lock_types import BoundedLockResult
from core.concurrency.protocols import AsyncContextManagerProtocol
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import publication_completion_deadline
from core.logging.trace import get_logger
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.runtime.backend_process_tracking_db import (
    cleanup_tracked_backend_processes_from_database,
)
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_STOPPED,
    ORCH_STATE_STOPPING,
)
from core.state.state_transition_sets import STOP_PROHIBITIVE_STATES
from core.tasks.api_events import send_task_complete_event
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.type_catalog import TASK_TYPE_BACKGROUND_JOB
from orchestrator.lifecycle.event_shutdown.internal_protocols import (
    ShutdownExecutionDependenciesProtocol,
)
from orchestrator.lifecycle.runtime_mutation_commands import RuntimeMutationStopRequest

__all__ = (
    "execute_stop_plugin_request",
    "resolve_registry",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.shutdown_request_execution"
OPERATION = "orchestrator.stop_plugin_locked"


def resolve_registry(
    deps: ShutdownExecutionDependenciesProtocol,
    registry: TaskRegistryProtocol | None,
) -> TaskRegistryProtocol:
    return registry if registry is not None else deps.task_registry


async def execute_stop_plugin_request(
    *,
    deps: ShutdownExecutionDependenciesProtocol,
    request: RuntimeMutationStopRequest,
    perform_plugin_stop_logic: Callable[[str], Awaitable[PluginStopOutcome]],
) -> PluginStopOutcome:
    logger = get_logger(LOGGER_NAME)
    plugin_name = request.plugin_name
    state_change_deadline = publication_completion_deadline()
    registry: TaskRegistryProtocol | None = None
    if (
        request.reply_channel is not None
        and isinstance(request.reply_channel, asyncio.Queue)
        and deps.task_registry.resolve_task_identity_for_reply_queue(request.reply_channel) is None
    ):
        registry = deps.task_registry
        await create(
            registry,
            task_type=TASK_TYPE_BACKGROUND_JOB,
            user_id=0,
            owner_id="system",
            owner_type="system",
            cancellation_id=create_system_cancellation_id(
                f"orchestrator_stop_plugin:{plugin_name}",
            ),
            status=TaskStatus.WORKING,
            progress_total=100,
            metadata={
                "operation": "plugin_stop",
                "plugin_name": plugin_name,
                "reason": request.reason,
                "force": request.force,
            },
            reply_queue=request.reply_channel,
        )
    cancel_completed = await deps.orchestrator.scheduler_start_task_tracker.cancel_and_wait(
        plugin_name=plugin_name,
        cancellation_coordinator=deps.orchestrator.cancellation_coordinator,
        reason=request.reason,
        timeout_sec=deps.orchestrator.config.get_float(
            "PLUGINS.STOP_START_TASK_CANCEL_TIMEOUT_SEC",
        ),
        logger=logger,
    )
    if not cancel_completed:
        logger.error(
            "Scheduler start task for plugin '%s' did not finish before stop continued.",
            plugin_name,
        )
    plugin_status = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
    if plugin_status in STOP_PROHIBITIVE_STATES:
        record = await deps.orchestrator.database_plugins.get_plugin_by_name(plugin_name)
        supports_process_tracking = bool(record and record.get("supports_backend_process_tracking"))
        if supports_process_tracking:
            cleanup_result = await cleanup_tracked_backend_processes_from_database(
                deps.orchestrator.database_plugins,
                plugin_name=plugin_name,
                logger=logger,
            )
            if cleanup_result is not None and (not cleanup_result.succeeded):
                message = (
                    f"Stop command for '{plugin_name}' refused: plugin in prohibitive state "
                    f"({plugin_status}) and tracked backend process cleanup failed."
                )
                logger.critical(message)
                if request.reply_channel is not None:
                    await send_task_complete_event(
                        request.reply_channel,
                        message,
                        success=False,
                        registry=resolve_registry(deps, registry),
                    )
                return PluginStopOutcome(
                    terminated=False,
                    message=message,
                )
        message = (
            f"Stop command for '{plugin_name}' ignored. Plugin in prohibitive state: "
            f"{plugin_status}."
        )
        logger.info(message)
        if request.reply_channel is not None:
            await send_task_complete_event(
                request.reply_channel,
                message,
                registry=resolve_registry(deps, registry),
            )
        return PluginStopOutcome(
            terminated=True,
            message=message,
        )
    lifecycle = deps.orchestrator.plugin_manager.lifecycle
    starting_receipt = None
    lock_failure_outcome: PluginStopOutcome | None = None
    pre_stop_outcome: PluginStopOutcome | None = None
    pre_stop_error_type: ErrorType | None = None
    lock_scope: (
        AsyncContextManagerProtocol[None] | AsyncContextManagerProtocol[BoundedLockResult]
    ) = lifecycle.plugin_lock_scope(plugin_name)
    if request.lock_acquire_timeout_sec is not None:
        lock_scope = lifecycle.bounded_plugin_lock_scope(
            plugin_name,
            timeout_seconds=request.lock_acquire_timeout_sec,
        )
    async with lock_scope as lock_result:
        if lock_result is not None and not lock_result.acquired:
            message = (
                f"Shutdown stop for plugin '{plugin_name}' could not acquire its lifecycle lock "
                f"within {request.lock_acquire_timeout_sec:.2f}s."
            )
            logger.error(message)
            lock_failure_outcome = PluginStopOutcome(
                terminated=False,
                message=message,
            )
        else:
            plugin_status = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
            if plugin_status in STOP_PROHIBITIVE_STATES:
                message = (
                    f"Stop command for '{plugin_name}' ignored after concurrent state change. "
                    f"Plugin in prohibitive state: {plugin_status}."
                )
                logger.info(message)
                pre_stop_outcome = PluginStopOutcome(
                    terminated=True,
                    message=message,
                )
            else:
                async with deps.state.plugins_context() as plugin_context:
                    plugin_state = plugin_context.plugin_states.get(plugin_name)
                    active_count = len(plugin_state.active_tasks) if plugin_state is not None else 0
                    finalize_pending = bool(plugin_state and plugin_state.finalize_pending)
                queue_sizes = await deps.capacity.get_queue_sizes([plugin_name])
                queued_count = queue_sizes.get(plugin_name, 0)
                active_or_queued = active_count > 0 or queued_count > 0
                if (not request.force) and (active_or_queued or finalize_pending):
                    finalization_text = " and finalization pending" if finalize_pending else ""
                    conflict_message = (
                        f"Cannot stop plugin '{plugin_name}': {active_count} active and "
                        f"{queued_count} queued tasks{finalization_text}."
                    )
                    logger.warning(conflict_message)
                    pre_stop_outcome = PluginStopOutcome(
                        terminated=False,
                        message=conflict_message,
                    )
                    pre_stop_error_type = ErrorType.CONFLICT
                else:
                    if request.force and (active_or_queued or finalize_pending):
                        logger.warning(
                            "FORCE STOP initiated for '%s'. %s active and %s queued tasks remain; finalization pending=%s.",
                            plugin_name,
                            active_count,
                            queued_count,
                            finalize_pending,
                        )
                    if request.publish_state_changes:
                        starting_receipt = (
                            await deps.lifecycle_publisher.publish_runtime_state_change(
                                plugin_name,
                                ORCH_STATE_STOPPING,
                                request.reason,
                            )
                        )
    if lock_failure_outcome is not None:
        if request.reply_channel is not None:
            await send_task_complete_event(
                request.reply_channel,
                lock_failure_outcome.message,
                success=False,
                registry=resolve_registry(deps, registry),
            )
        return lock_failure_outcome
    if pre_stop_outcome is not None:
        if request.reply_channel is not None:
            if pre_stop_error_type is None:
                await send_task_complete_event(
                    request.reply_channel,
                    pre_stop_outcome.message,
                    registry=resolve_registry(deps, registry),
                )
            else:
                await send_error_event_and_finalize(
                    request.reply_channel,
                    pre_stop_outcome.message,
                    pre_stop_error_type,
                    registry=resolve_registry(deps, registry),
                )
        return pre_stop_outcome
    if request.wait_for_state_changes and starting_receipt is not None:
        await starting_receipt.wait_for_completion(state_change_deadline)
    try:
        stop_outcome = await perform_plugin_stop_logic(plugin_name)
        if request.publish_state_changes:
            final_state = ORCH_STATE_STOPPED if stop_outcome.terminated else ORCH_STATE_ERROR
            final_reason = (
                "Plugin stop process completed."
                if stop_outcome.terminated
                else (stop_outcome.message or "Plugin stop process failed.")
            )
            final_receipt = await deps.lifecycle_publisher.publish_runtime_state_change(
                plugin_name,
                final_state,
                final_reason,
            )
            if request.wait_for_state_changes and final_receipt is not None:
                await final_receipt.wait_for_completion(state_change_deadline)
        if request.reply_channel is not None:
            completion_message = (
                f"Plugin '{plugin_name}' has been stopped."
                if stop_outcome.terminated
                else (stop_outcome.message or f"Plugin '{plugin_name}' could not be stopped.")
            )
            await send_task_complete_event(
                request.reply_channel,
                completion_message,
                success=stop_outcome.terminated,
                registry=resolve_registry(deps, registry),
            )
        return stop_outcome
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Critical error during plugin stop process for {plugin_name}",
            operation=OPERATION,
        )
        public_message = project_public_exception(exception).message
        if request.publish_state_changes:
            await deps.lifecycle_publisher.publish_runtime_state_change(
                plugin_name,
                ORCH_STATE_ERROR,
                public_message,
            )
        if request.reply_channel is not None:
            await send_task_complete_event(
                request.reply_channel,
                public_message,
                success=False,
                error_code=500,
                registry=resolve_registry(deps, registry),
            )
        return PluginStopOutcome(
            terminated=False,
            message=public_message,
        )
