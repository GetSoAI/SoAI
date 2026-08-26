"""SoAI - Stale/orphan orchestrated task recovery loop [backend/orchestrator/control/stale_task_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.periodic import run_periodic_task
from core.tasks.task import Task
from core.timing.epoch import epoch_ms
from orchestrator.control.task_recovery_actions import (
    durably_requeue_and_refresh_task,
    recover_cancelled_task_without_context,
    recover_failed_task_without_context,
)
from orchestrator.control.task_recovery_dependencies import (
    OrchestratedTaskRecoveryDependencies,
)
from orchestrator.control.task_recovery_policy import (
    is_stale_orphan_recoverable,
    resolve_stale_recovery_interval_seconds,
)
from orchestrator.control.task_recovery_resolver import OrchestratedTaskRecoveryResolver

__all__ = ("OrchestratedStaleTaskRecovery",)

LOGGER_NAME = "SoAI.orchestrator.control.stale_task_recovery"
OPERATION = "orchestrator.control.task_recovery"


class OrchestratedStaleTaskRecovery:
    def __init__(self, deps: OrchestratedTaskRecoveryDependencies) -> None:
        self._deps = deps
        self._resolver = OrchestratedTaskRecoveryResolver(deps)

    async def recovery_loop(self) -> None:
        logger = get_logger(LOGGER_NAME)
        interval_seconds = resolve_stale_recovery_interval_seconds(
            self._deps.task_registry.stuck_task_timeout_ms,
        )
        await run_periodic_task(
            self._deps.task_registry.shutdown_event,
            interval_seconds,
            self._run_recovery_pass,
            logger=logger,
            task_name="orchestrated_task_recovery",
        )

    async def _recover_orphaned_task(self, task: Task, *, prefetched_task_ids: set[str]) -> bool:
        logger = get_logger(LOGGER_NAME)
        if task.status.is_terminal():
            return False
        context = task.orchestration_context
        if context is None:
            if task.cancellation_requested_at_ms is not None:
                reason = await self._resolver.resolve_cancellation_reason(task)
                recovered = await recover_cancelled_task_without_context(
                    self._deps,
                    self._resolver,
                    task,
                    reason,
                )
                if not recovered:
                    return False
                logger.warning(
                    "Cancelled orphaned orchestrated task without orchestration context: %s",
                    task.task_id,
                )
            else:
                reason = "Task lost orchestration context while still active."
                recovered = await recover_failed_task_without_context(
                    self._deps,
                    self._resolver,
                    task,
                    error_message=reason,
                    status_message=reason,
                )
                if not recovered:
                    return False
                logger.warning(
                    "Failed orphaned orchestrated task without orchestration context: %s",
                    task.task_id,
                )
            return True
        tracking_id = context.tracking_id
        if tracking_id and await self._deps.active_inferences.is_tracking_id_active(tracking_id):
            return False
        if await self._deps.queue.tracking.has_task_ownership(task):
            return False
        if task.cancellation_requested_at_ms is not None:
            reason = await self._resolver.resolve_cancellation_reason(task)
            await self._deps.outcomes.cancel_task(task, reason)
            logger.warning("Cancelled orphaned orchestrated task %s.", task.task_id)
            return True
        if task.task_id in prefetched_task_ids:
            requeued = await durably_requeue_and_refresh_task(
                self._deps,
                task,
                logger=logger,
                operation=OPERATION,
                status_message="Requeued after stranded durable prefetch",
                failure_message="Failed to requeue stranded prefetched orchestrated task.",
            )
            if requeued:
                logger.warning("Requeued stranded prefetched orchestrated task %s.", task.task_id)
                return True
            await self._deps.outcomes.fail_task(
                task,
                "Task could not be requeued after stranded durable prefetch.",
                allow_failover=False,
            )
            logger.warning("Failed stranded prefetched orchestrated task %s.", task.task_id)
            return True
        if not is_stale_orphan_recoverable(
            task,
            stuck_task_timeout_ms=self._deps.task_registry.stuck_task_timeout_ms,
            current_epoch_ms=epoch_ms(),
        ):
            return False
        requeued = await durably_requeue_and_refresh_task(
            self._deps,
            task,
            logger=logger,
            operation=OPERATION,
            status_message="Requeued after losing orchestrator ownership",
            failure_message="Failed to requeue stale orchestrated task after losing ownership.",
        )
        if requeued:
            logger.warning("Requeued stale orphaned orchestrated task %s.", task.task_id)
            return True
        await self._deps.outcomes.fail_task(
            task,
            "Task timed out after losing orchestrator ownership.",
            allow_failover=False,
        )
        logger.warning("Failed stale orphaned orchestrated task %s.", task.task_id)
        return True

    async def _run_recovery_pass(self) -> None:
        logger = get_logger(LOGGER_NAME)
        recovered = 0
        tasks = await self._resolver.query_active_orchestrated_tasks()
        prefetched_task_ids = set(
            await self._deps.task_registry.database_tasks.query_prefetched_orchestrated_task_ids(),
        )
        for task in tasks:
            try:
                if await self._recover_orphaned_task(task, prefetched_task_ids=prefetched_task_ids):
                    recovered += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to recover orphaned orchestrated task.",
                    operation=OPERATION,
                    details={"task_id": task.task_id},
                    level="warning",
                )
        if recovered > 0:
            logger.warning("Recovered %d orphaned orchestrated task(s).", recovered)
