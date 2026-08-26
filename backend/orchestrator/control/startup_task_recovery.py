"""SoAI - Startup recovery for orchestrated tasks [backend/orchestrator/control/startup_task_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.task import Task
from orchestrator.control.task_recovery_actions import (
    durably_requeue_and_refresh_task,
    recover_cancelled_task_without_context,
    recover_failed_task_without_context,
)
from orchestrator.control.task_recovery_dependencies import (
    OrchestratedTaskRecoveryDependencies,
)
from orchestrator.control.task_recovery_policy import is_startup_orphan_recoverable
from orchestrator.control.task_recovery_resolver import OrchestratedTaskRecoveryResolver

__all__ = ("OrchestratedStartupTaskRecovery",)

LOGGER_NAME = "SoAI.orchestrator.control.startup_task_recovery"
OPERATION = "orchestrator.control.task_recovery.startup"


class OrchestratedStartupTaskRecovery:
    def __init__(self, deps: OrchestratedTaskRecoveryDependencies) -> None:
        self._deps = deps
        self._resolver = OrchestratedTaskRecoveryResolver(deps)

    async def fail_startup_orphaned_tasks(self, *, started_at_epoch_ms: int) -> int:
        logger = get_logger(LOGGER_NAME)
        recovered = 0
        tasks = await self._resolver.query_active_orchestrated_tasks()
        for task in tasks:
            if not is_startup_orphan_recoverable(
                task,
                started_at_epoch_ms=started_at_epoch_ms,
            ):
                continue
            try:
                if await self._recover_startup_orphan(task):
                    recovered += 1
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to fail startup-orphaned orchestrated task.",
                    operation=OPERATION,
                    details={"task_id": task.task_id},
                    level="warning",
                )
        return recovered

    async def _recover_startup_orphan(self, task: Task) -> bool:
        if task.cancellation_requested_at_ms is not None:
            reason = await self._resolver.resolve_cancellation_reason(task)
            if task.orchestration_context is None:
                return await recover_cancelled_task_without_context(
                    self._deps,
                    self._resolver,
                    task,
                    reason,
                )
            await self._deps.outcomes.cancel_task(task, reason)
            return True
        if task.orchestration_context is None:
            return await recover_failed_task_without_context(
                self._deps,
                self._resolver,
                task,
                error_message="Server restarted while task was in-flight",
                status_message="Request interrupted by server restart",
            )
        if await self._requeue_orchestrated_task(task):
            return True
        await self._deps.outcomes.fail_task(
            task,
            "Server restarted while task was in-flight",
            allow_failover=False,
        )
        return True

    async def _requeue_orchestrated_task(self, task: Task) -> bool:
        logger = get_logger(LOGGER_NAME)
        return await durably_requeue_and_refresh_task(
            self._deps,
            task,
            logger=logger,
            operation=OPERATION,
            status_message="Requeued after server restart",
            failure_message="Failed to durably requeue orchestrated task during startup recovery.",
        )
