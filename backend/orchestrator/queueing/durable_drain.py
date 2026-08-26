"""SoAI - Durable queue drain loop for orchestrated inference [backend/orchestrator/queueing/durable_drain.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import uuid

from core.database.task_requests import (
    DurableQueueClaim,
    durable_queue_claim_scheduling_key,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.request_priority import RequestPriority
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.task import Task
from core.timing.epoch import epoch_ms
from orchestrator.queueing.durable_replay import restore_durable_inference_event
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("durable_queue_drain_loop",)

LOGGER_NAME = "SoAI.orchestrator.queueing.durable_drain"
OPERATION_ORCHESTRATOR_DURABLE_QUEUE_DRAIN_LOOP = "orchestrator.durable_queue.drain_loop"
OPERATION_ORCHESTRATOR_DURABLE_QUEUE_ENQUEUE_CLAIMED_TASK = (
    "orchestrator.durable_queue.enqueue_claimed_task"
)
OPERATION_ORCHESTRATOR_DURABLE_QUEUE_REPLAY = "orchestrator.durable_queue.replay"
DURABLE_QUEUE_CANCEL_REASON = "Task was cancelled while queued."


async def durable_queue_drain_loop(queue: QueueServiceView) -> None:
    logger = get_logger(LOGGER_NAME)
    lease_owner = f"orchestrator:{uuid.uuid4().hex}"
    config = queue.config
    lease_ttl_ms = int(config.durable_queue_lease_ttl_sec * 1000.0)
    wake_timeout = float(config.durable_queue_recovery_sweep_sec)
    prefetch_window = int(config.plugin_prefetch_window_default)
    database_tasks = queue.task_registry.database_tasks
    while not queue.shutdown_event.is_set():
        try:
            await database_tasks.recover_expired_orchestrator_queue_items(now_ms=epoch_ms())
            priority_counts = await queue.get_prefetched_priority_counts()
            claimed_items: list[DurableQueueClaim] = []
            for request_priority in RequestPriority:
                claim_limit = max(0, prefetch_window - priority_counts[request_priority])
                if claim_limit <= 0:
                    continue
                priority_claims = await database_tasks.claim_orchestrator_queue_items(
                    now_ms=epoch_ms(),
                    lease_owner=lease_owner,
                    lease_ttl_ms=lease_ttl_ms,
                    limit=claim_limit,
                    request_priority=request_priority,
                )
                claimed_items.extend(priority_claims)
            if claimed_items:
                claimed_items.sort(key=durable_queue_claim_scheduling_key)
                await _enqueue_claimed_tasks(
                    queue,
                    [claimed_item.task_id for claimed_item in claimed_items],
                    lease_owner=lease_owner,
                )
            else:
                await _await_durable_wakeup(queue, wake_timeout)
        except asyncio.CancelledError:
            break
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Durable queue drain pass failed.",
                operation=OPERATION_ORCHESTRATOR_DURABLE_QUEUE_DRAIN_LOOP,
                level="warning",
            )
            await asyncio.sleep(wake_timeout)


async def _await_durable_wakeup(queue: QueueServiceView, wake_timeout: float) -> None:
    try:
        await asyncio.wait_for(queue.durable_queue_wakeup.wait(), timeout=wake_timeout)
    except TimeoutError:
        return
    finally:
        queue.clear_durable_queue_wakeup()


async def _enqueue_claimed_tasks(
    queue: QueueServiceView,
    claimed_task_ids: list[str],
    *,
    lease_owner: str,
) -> None:
    database_tasks = queue.task_registry.database_tasks
    loaded_tasks = await queue.task_registry.get_many(tuple(claimed_task_ids), force_refresh=True)
    loaded_tasks_by_id = {task.task_id: task for task in loaded_tasks}
    for task_id in claimed_task_ids:
        task = loaded_tasks_by_id.get(task_id)
        if task is not None:
            await _enqueue_claimed_task(queue, task, lease_owner=lease_owner)
            continue
        logger = get_logger(LOGGER_NAME)
        logger.warning(
            "Durable queue item references missing task [%s]. Finalizing queue item as failed.",
            task_id,
        )
        await database_tasks.finalize_orchestrator_queue_item(task_id, "failed")
        await queue.tracking.forget_task(task_id)


async def _enqueue_claimed_task(queue: QueueServiceView, task: Task, *, lease_owner: str) -> None:
    logger = get_logger(LOGGER_NAME)
    database_tasks = queue.task_registry.database_tasks
    task_id = task.task_id
    if task.status.is_terminal():
        await database_tasks.finalize_orchestrator_queue_item(task.task_id, task.status.value)
        await _cleanup_failed_claim(queue, task)
        return
    if await _cancel_claimed_task_if_requested(queue, task):
        return
    try:
        task = restore_durable_inference_event(task)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Accepted task could not be replayed from durable orchestration state.",
            operation=OPERATION_ORCHESTRATOR_DURABLE_QUEUE_REPLAY,
            details={"task_id": task_id},
            level="error",
        )
        await finalize(
            queue.task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=503,
            error_message="Durable orchestration replay failed.",
            status_message="Durable orchestration replay failed.",
        )
        await _cleanup_failed_claim(queue, task)
        return
    await queue.task_registry.update_task_cache(task)
    if await queue.tracking.has_task_ownership(task):
        await database_tasks.mark_orchestrator_queue_item_running_if_leased(
            task.task_id,
            lease_owner=lease_owner,
        )
        return
    try:
        marked = await database_tasks.mark_orchestrator_queue_item_prefetched_if_leased(
            task.task_id,
            lease_owner=lease_owner,
        )
        if not marked:
            await _cleanup_failed_claim(queue, task)
            return
        await queue.tracking.register_indexed_active_task(task)
        await queue.priority.enqueue_task(task)
    except asyncio.CancelledError:
        await _cleanup_failed_claim(queue, task)
        await database_tasks.release_orchestrator_queue_item_lease(
            task.task_id,
            available_at_ms=epoch_ms(),
        )
        raise
    except ServiceUnavailableError:
        await _cleanup_failed_claim(queue, task)
        await database_tasks.release_orchestrator_queue_item_lease(
            task.task_id,
            available_at_ms=epoch_ms(),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to move durable task into in-memory prefetch queue.",
            operation=OPERATION_ORCHESTRATOR_DURABLE_QUEUE_ENQUEUE_CLAIMED_TASK,
            details={"task_id": task.task_id},
            level="warning",
        )
        await _cleanup_failed_claim(queue, task)
        await database_tasks.release_orchestrator_queue_item_lease(
            task.task_id,
            available_at_ms=epoch_ms(),
        )


async def _cleanup_failed_claim(queue: QueueServiceView, task: Task) -> None:
    await queue.tracking.forget_task(task.task_id)


async def _cancel_claimed_task_if_requested(queue: QueueServiceView, task: Task) -> bool:
    decision = await queue.cancel_if_cancelled(task, reason=DURABLE_QUEUE_CANCEL_REASON)
    if decision is None:
        return False
    reason = decision.reason or DURABLE_QUEUE_CANCEL_REASON
    await finalize(
        queue.task_registry,
        task.task_id,
        TaskStatus.CANCELLED,
        error_message=reason,
        status_message=reason,
    )
    await _cleanup_failed_claim(queue, task)
    return True
