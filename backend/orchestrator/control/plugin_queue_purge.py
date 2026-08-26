"""SoAI - Orchestrator queue purge helpers for plugin lifecycle actions [backend/orchestrator/control/plugin_queue_purge.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from core.tasks.cancellation_ids import is_system_cancellation_id
from core.timing.epoch import epoch_ms
from orchestrator.control.plugin_queue_purge_dependencies import (
    PluginQueuePurgeDependencies,
)
from orchestrator.control.plugin_queue_purge_partitioning import (
    partition_tasks_by_primary_plugin,
)
from orchestrator.durable_requeue import durably_requeue_or_release_after_plugin_purge

if TYPE_CHECKING:
    from typing import Literal

__all__ = (
    "purge_all_requests_from_global_queues",
    "purge_plugin_requests_from_global_queues",
)

LOGGER_NAME = "SoAI.orchestrator.control.plugin_queue_purge"
OPERATION = "orchestrator.control.plugin_queue_purge.requeue_in_memory"


async def purge_plugin_requests_from_global_queues(
    *,
    deps: PluginQueuePurgeDependencies,
    plugin_name: str,
    purge_reason: str,
    fail_reason: str,
    error_type: ErrorType,
    operation: str,
    allow_failover: bool,
) -> None:
    await deps.scheduler.dispatching.begin_plugin_purge(plugin_name, reason=purge_reason)
    logger = get_logger(LOGGER_NAME)
    try:
        await deps.active_inferences.fail_active_tasks(
            plugin_name,
            fail_reason,
            allow_failover=allow_failover,
            error_type=error_type,
        )
        await deps.scheduler.dispatching.cancel_and_drain_plugin_queue(
            plugin_name,
            reason=purge_reason,
        )
        queue_snapshot = await deps.queue.priority.drain_task_queue()
        pending_universal_ids = list(
            await deps.queue.tracking.get_pending_universal_ids_for_plugins({plugin_name}),
        )
        tasks_to_requeue, tasks_to_fail = await partition_tasks_by_primary_plugin(
            orchestrator=deps.orchestrator,
            queue=deps.queue,
            plugin_name=plugin_name,
            tasks=queue_snapshot,
            operation=operation,
        )
        durable_requeue_requested = False
        available_at_ms = epoch_ms()
        for task in tasks_to_requeue:
            durable_requeue_requested = (
                await durably_requeue_or_release_after_plugin_purge(
                    deps.queue,
                    deps.queue.task_registry,
                    task=task,
                    outcomes=deps.outcomes,
                    logger=logger,
                    operation=OPERATION,
                    allow_failover=allow_failover,
                    available_at_ms=available_at_ms,
                )
                or durable_requeue_requested
            )
        if durable_requeue_requested:
            deps.queue.notify_durable_queue_wakeup()
        if tasks_to_fail:
            fail_tasks = [
                deps.outcomes.fail_task(
                    task=task,
                    reason=fail_reason,
                    allow_failover=allow_failover,
                    error_type=error_type,
                )
                for task in tasks_to_fail
            ]
            await asyncio.gather(*fail_tasks, return_exceptions=False)
        if pending_universal_ids:
            fail_waiter_tasks = [
                deps.outcomes.fail_waiters(
                    routing_key=universal_id,
                    reason=fail_reason,
                    allow_failover=allow_failover,
                    error_type=error_type,
                )
                for universal_id in pending_universal_ids
            ]
            await asyncio.gather(*fail_waiter_tasks, return_exceptions=False)
    finally:
        await deps.scheduler.dispatching.finish_plugin_purge(plugin_name)


async def purge_all_requests_from_global_queues(
    *,
    deps: PluginQueuePurgeDependencies,
    terminal_reason: str,
    terminal_status: Literal["cancelled", "failed"] = "failed",
) -> None:
    logger = get_logger(LOGGER_NAME)
    tracking = deps.queue.tracking
    cancellation_ids = await tracking.get_cancellation_ids_snapshot()
    cancellation_ids = {
        cancellation_id
        for cancellation_id in cancellation_ids
        if cancellation_id and not is_system_cancellation_id(cancellation_id)
    }
    cancel_tasks = [
        deps.orchestrator.cancellation_coordinator.cancel_scope(
            cancellation_id=cancellation_id,
            reason=terminal_reason,
        )
        for cancellation_id in cancellation_ids
    ]
    await deps.scheduler.dispatching.begin_global_purge(reason=terminal_reason)
    try:
        cancellation_results = await asyncio.gather(
            deps.scheduler.dispatching.cancel_all_plugin_queue_dispatchers(),
            *cancel_tasks,
            return_exceptions=True,
        )
        for cancellation_result in cancellation_results:
            if isinstance(cancellation_result, asyncio.CancelledError):
                raise cancellation_result
            if isinstance(cancellation_result, BaseException):
                log_handled_exception(
                    logger,
                    cancellation_result,
                    message="Global purge cancellation task raised (non-critical).",
                    operation=OPERATION,
                )
        tasks_to_finalize = await deps.queue.priority.drain_task_queue()
        pending_keys = await tracking.get_pending_keys()
        dedup_waiters = await deps.queue.dedup_requeue.drain_dedup_waiters(
            reason=terminal_reason,
        )
        tasks_to_finalize.extend(dedup_waiters)
        if tasks_to_finalize:
            deduped_tasks = {task.task_id: task for task in tasks_to_finalize if task is not None}
            if terminal_status == "cancelled":
                terminal_tasks = [
                    deps.outcomes.cancel_task(task=task, reason=terminal_reason)
                    for task in deduped_tasks.values()
                ]
            else:
                terminal_tasks = [
                    deps.outcomes.fail_task(
                        task=task,
                        reason=terminal_reason,
                        allow_failover=False,
                    )
                    for task in deduped_tasks.values()
                ]
            await asyncio.gather(*terminal_tasks, return_exceptions=False)
            await deps.queue.deduplication.complete_resolution(
                [task.task_id for task in dedup_waiters],
                [],
            )
        if pending_keys:
            if terminal_status == "cancelled":
                waiter_tasks = [
                    deps.outcomes.cancel_waiters(
                        routing_key=key,
                        reason=terminal_reason,
                    )
                    for key in pending_keys
                ]
            else:
                waiter_tasks = [
                    deps.outcomes.fail_waiters(
                        routing_key=key,
                        reason=terminal_reason,
                        allow_failover=False,
                    )
                    for key in pending_keys
                ]
            await asyncio.gather(*waiter_tasks, return_exceptions=False)
        active_snapshot = await deps.active_inferences.get_active_inferences_snapshot()
        active_tracking_ids = [
            tracking_id
            for info in active_snapshot
            if isinstance((tracking_id := info.get("tracking_id")), str) and tracking_id
        ]
        if active_tracking_ids:
            if terminal_status == "cancelled":
                terminal_tasks = [
                    deps.active_inferences.cancel_inflight_task(
                        tracking_id=tracking_id,
                        reason=terminal_reason,
                    )
                    for tracking_id in active_tracking_ids
                ]
            else:
                terminal_tasks = [
                    deps.active_inferences.fail_inflight_task(
                        tracking_id=tracking_id,
                        reason=terminal_reason,
                        allow_failover=False,
                    )
                    for tracking_id in active_tracking_ids
                ]
            await asyncio.gather(*terminal_tasks, return_exceptions=False)
    finally:
        await deps.scheduler.dispatching.finish_global_purge()
    logger.info("Global work queues purged.")
