"""SoAI - Shared orchestrated task recovery actions [backend/orchestrator/control/task_recovery_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from core.tasks.task import Task
from orchestrator.control.task_recovery_dependencies import (
    OrchestratedTaskRecoveryDependencies,
)
from orchestrator.control.task_recovery_resolver import OrchestratedTaskRecoveryResolver
from orchestrator.durable_requeue import durably_requeue_task

__all__ = (
    "durably_requeue_and_refresh_task",
    "recover_cancelled_task_without_context",
    "recover_failed_task_without_context",
)


async def recover_cancelled_task_without_context(
    deps: OrchestratedTaskRecoveryDependencies,
    resolver: OrchestratedTaskRecoveryResolver,
    task: Task,
    reason: str,
) -> bool:
    resolved_task, has_live_ownership = await resolver.resolve_unowned_tracked_task(task)
    if has_live_ownership:
        return False
    if resolved_task is None:
        await resolver.finalize_without_context(
            task,
            TaskStatus.CANCELLED,
            error_message=reason,
            status_message=reason,
        )
        return True
    await deps.outcomes.cancel_task(resolved_task, reason)
    return True


async def recover_failed_task_without_context(
    deps: OrchestratedTaskRecoveryDependencies,
    resolver: OrchestratedTaskRecoveryResolver,
    task: Task,
    *,
    error_message: str,
    status_message: str,
) -> bool:
    resolved_task, has_live_ownership = await resolver.resolve_unowned_tracked_task(task)
    if has_live_ownership:
        return False
    if resolved_task is None:
        await resolver.finalize_without_context(
            task,
            TaskStatus.FAILED,
            error_code=503,
            error_message=error_message,
            status_message=status_message,
        )
        return True
    await deps.outcomes.fail_task(resolved_task, error_message, allow_failover=False)
    return True


async def durably_requeue_and_refresh_task(
    deps: OrchestratedTaskRecoveryDependencies,
    task: Task,
    *,
    logger: LoggerProtocol,
    operation: str,
    status_message: str,
    failure_message: str,
) -> bool:
    requeued = await durably_requeue_task(
        deps.queue,
        deps.task_registry,
        task,
        logger=logger,
        operation=operation,
        status_message=status_message,
        failure_message=failure_message,
    )
    if not requeued:
        return False
    refreshed_task = await deps.task_registry.get(task.task_id, force_refresh=True)
    if refreshed_task is not None:
        await deps.task_registry.update_task_cache(refreshed_task)
    return True
