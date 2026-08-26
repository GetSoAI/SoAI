"""SoAI - Deduplication cleanup and stale waiter requeue for orchestrator queueing [backend/orchestrator/queueing/dedup_requeue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace

from core.di.validation import require_dependencies
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ServiceUnavailableError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.protocols_queue import QueueCycleType
from core.tasks.enums import TaskStatus
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.orchestration_context_cache import merge_orchestration_context_snapshot
from core.tasks.periodic import run_periodic_task
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from orchestrator.queueing.deduplication import QueueDeduplication
from orchestrator.queueing.internal_protocols import (
    QueueRequestTrackingProtocol,
    QueueServiceView,
)
from orchestrator.requeue_attempts import RequeueAttemptSpec, execute_requeue_attempt
from orchestrator.requeue_preparation import (
    is_requeue_blocked_by_delivery,
)

__all__ = (
    "QueueDeduplicationRequeue",
    "QueueDeduplicationRequeueDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.queueing.dedup_requeue"
OPERATION = "orchestrator_queue.requeue_stale_dedup_waiters"


@dataclass(frozen=True, slots=True)
class QueueDeduplicationRequeueDependencies:
    deduplication: QueueDeduplication
    shutdown_event: asyncio.Event
    task_registry: TaskRegistryProtocol
    task_queue: QueueServiceView
    task_index: QueueRequestTrackingProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="QueueDeduplicationRequeueDependencies",
            deduplication=self.deduplication,
            shutdown_event=self.shutdown_event,
            task_index=self.task_index,
            task_queue=self.task_queue,
            task_registry=self.task_registry,
        )


class QueueDeduplicationRequeue:
    def __init__(self, deps: QueueDeduplicationRequeueDependencies) -> None:
        self._deps = deps

    async def drain_dedup_waiters(self, *, reason: str) -> list[Task]:
        waiter_ids = await self._deps.deduplication.drain_waiters(reason=reason)
        waiters = await self._deps.task_index.get_tasks_by_ids(waiter_ids)
        deduped = await self._deps.task_index.get_tasks_by_status(TaskStatus.DEDUPED)
        combined = {task.task_id: task for task in (waiters + deduped)}
        combined_task_ids = list(combined)
        await self._deps.deduplication.complete_resolution(
            combined_task_ids,
            combined_task_ids,
        )
        return list(combined.values())

    async def dedup_cleanup_loop(self) -> None:
        logger = get_logger(LOGGER_NAME)
        await run_periodic_task(
            self._deps.shutdown_event,
            300,
            self._perform_dedup_cleanup,
            logger=logger,
            task_name="deduplication_cleanup",
        )

    async def _perform_dedup_cleanup(self) -> None:
        stale_task_ids, stale_reason = await self._deps.deduplication.cleanup_expired_entries()
        if stale_task_ids and stale_reason:
            unresolved_waiter_ids = await self.requeue_stale_dedup_waiters(
                stale_task_ids,
                reason=stale_reason,
            )
            await self._deps.deduplication.complete_resolution(
                stale_task_ids,
                unresolved_waiter_ids,
            )

    async def requeue_stale_dedup_waiters(
        self,
        task_ids: list[str],
        *,
        reason: str,
    ) -> list[str]:
        logger = get_logger(LOGGER_NAME)
        registry = self._deps.task_registry
        unique_task_ids = [task_id for task_id in dict.fromkeys(task_ids) if task_id]
        if not unique_task_ids:
            return []
        tasks_to_requeue: list[Task] = []
        tasks_missing_event: list[Task] = []
        unresolved_waiter_ids: list[str] = []
        for task_id in unique_task_ids:
            try:
                task = await self._deps.task_index.get_task_by_id(task_id)
                if task is None or task.status.is_terminal():
                    continue
                if task.status != TaskStatus.DEDUPED:
                    continue
                context = task.orchestration_context
                if context is None or context.event is None:
                    tasks_missing_event.append(task)
                    continue
                context = replace(
                    context,
                    dedup_hash=None,
                    dedup_lead_task_id=None,
                )
                task = task.with_orchestration_context(context)
                await self._deps.task_index.update_task(task)
                tasks_to_requeue.append(await merge_orchestration_context_snapshot(registry, task))
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to prepare deduplicated task recovery.",
                    operation=OPERATION,
                    details={"task_id": task_id, "reason": reason},
                    level="warning",
                )
                unresolved_waiter_ids.append(task_id)
        if not tasks_to_requeue and not tasks_missing_event:
            return unresolved_waiter_ids
        failures: list[Task] = []
        failures.extend(tasks_missing_event)
        for task in tasks_to_requeue:
            if task.status.is_terminal():
                continue
            context = task.orchestration_context
            if context is None or context.event is None:
                failures.append(task)
                continue
            try:
                requeue_result = await execute_requeue_attempt(
                    self._deps.task_queue,
                    registry,
                    task,
                    spec=RequeueAttemptSpec(
                        logger=logger,
                        operation="orchestrator.dedup_timeout_requeue.persist",
                        close_priority_cycle=True,
                        close_plugin_cycle=False,
                        prepare_task=True,
                    ),
                )
                requeued_task = requeue_result.task
                context = requeued_task.orchestration_context
                if (
                    context is not None and is_requeue_blocked_by_delivery(context)
                ) or requeue_result.blocked_by_delivery:
                    failures.append(requeued_task)
                    continue
                if requeue_result.requeued:
                    logger.warning(
                        "Re-queued deduplicated task [%s] after dedup lead timeout: %s",
                        task.task_id,
                        reason,
                    )
                    continue
                if task.status.is_terminal():
                    continue
                failures.append(task)
            except ServiceUnavailableError:
                failures.append(task)
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to re-queue deduplicated task after lead timeout (non-critical).",
                    operation=OPERATION,
                    details={"task_id": task.task_id, "reason": reason},
                    level="debug",
                )
                failures.append(task)
        if failures:
            for task in failures:
                try:
                    context = self._deps.task_queue.require_orchestration_context(task)
                    await self._deps.task_queue.cycles.close_cycle(
                        task,
                        QueueCycleType.PRIORITY,
                        context_label="dedup_timeout_cleanup",
                    )
                    await send_error_event_and_finalize(
                        task.reply_queue,
                        reason,
                        ErrorType.SERVER_ERROR,
                        registry=registry,
                        context=(context.event.context if context.event is not None else None),
                        task_id=task.task_id,
                    )
                    refreshed_task = await registry.get(task.task_id, force_refresh=True)
                    if refreshed_task is not None and not refreshed_task.status.is_terminal():
                        unresolved_waiter_ids.append(task.task_id)
                        continue
                    await self._deps.task_queue.tracking.cleanup_completed_task(task)
                except HANDLED_RUNTIME_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to terminally finalize deduplicated task recovery.",
                        operation=OPERATION,
                        details={"task_id": task.task_id, "reason": reason},
                        level="warning",
                    )
                    unresolved_waiter_ids.append(task.task_id)
        return list(dict.fromkeys(unresolved_waiter_ids))
