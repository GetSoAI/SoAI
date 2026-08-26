"""SoAI - Scheduler dispatch rejection ownership cleanup [backend/orchestrator/scheduling/dispatch_rejections.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.tasks.task import Task
from orchestrator.requeue_ownership import release_task_execution_ownership
from orchestrator.scheduling.dispatch_shutdown import fail_purged_dispatch
from orchestrator.scheduling.dispatching_dependencies import (
    SchedulerDispatchingDependencies,
)
from orchestrator.scheduling.purge_state import PurgeStateSnapshot

__all__ = (
    "fail_released_dispatch_task",
    "fail_released_purged_dispatch",
    "release_dispatch_admission_ownership",
)


async def release_dispatch_admission_ownership(
    deps: SchedulerDispatchingDependencies,
    task: Task,
) -> Task:
    return await release_task_execution_ownership(
        deps.queue,
        deps.task_registry,
        task,
        close_priority_cycle=False,
        close_plugin_cycle=False,
    )


async def fail_released_dispatch_task(
    deps: SchedulerDispatchingDependencies,
    task: Task,
    reason: str,
    *,
    allow_failover: bool,
    error_type: ErrorType = ErrorType.SERVER_ERROR,
) -> None:
    released_task = await release_dispatch_admission_ownership(deps, task)
    await deps.outcomes.fail_task(
        released_task,
        reason,
        allow_failover=allow_failover,
        error_type=error_type,
    )


async def fail_released_purged_dispatch(
    *,
    deps: SchedulerDispatchingDependencies,
    task: Task,
    plugin_name: str,
    purge_snapshot: PurgeStateSnapshot,
) -> None:
    released_task = await release_dispatch_admission_ownership(deps, task)
    await fail_purged_dispatch(
        task=released_task,
        plugin_name=plugin_name,
        purge_snapshot=purge_snapshot,
        deps=deps,
    )
