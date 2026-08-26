"""SoAI - Orchestrator control startup background task wiring [backend/orchestrator/control/startup_background_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine

from core.orchestrator.queue_decisions import QueueDecision
from core.tasks.protocols import SpawnTrackedBackgroundTaskCallable
from orchestrator.control import config_management
from orchestrator.control.internal_protocols import (
    LifecycleCircuitBreakerSurface,
    SchedulerLoopSurface,
)
from orchestrator.control.planner_worker_spawning import spawn_planner_worker
from orchestrator.queueing.durable_drain import durable_queue_drain_loop
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("start_control_background_tasks",)


async def start_control_background_tasks(
    *,
    spawn_tracked_background_task: SpawnTrackedBackgroundTaskCallable,
    queue: QueueServiceView,
    scheduler: SchedulerLoopSurface,
    lifecycle: LifecycleCircuitBreakerSurface,
    decision_handler: Callable[[QueueDecision], Awaitable[None]],
    stale_task_recovery_loop: Callable[[], Coroutine[None, None, None]],
    num_planner_workers: int,
    config_deps: config_management.OrchestratorConfigManagementDependencies,
) -> tuple[int, int]:
    planner_worker_count = 0
    planner_worker_next_id = 0
    for worker_id in range(num_planner_workers):
        await spawn_planner_worker(
            spawn_background_task=spawn_tracked_background_task,
            queue=queue,
            worker_id=worker_id,
            decision_handler=decision_handler,
        )
        planner_worker_count += 1
        planner_worker_next_id = max(planner_worker_next_id, worker_id + 1)
    _ = await spawn_tracked_background_task(
        coro=scheduler.scheduler_loop(),
        owner="scheduler_loop",
        name="orchestrator-scheduler_loop",
    )
    _ = await spawn_tracked_background_task(
        coro=lifecycle.circuit_breakers.persist_dirty_states_loop(),
        owner="persist_dirty_states",
        name="orchestrator-persist_dirty_states",
    )
    _ = await spawn_tracked_background_task(
        coro=queue.dedup_requeue.dedup_cleanup_loop(),
        owner="dedup_cleanup",
        name="orchestrator-dedup_cleanup",
    )
    _ = await spawn_tracked_background_task(
        coro=durable_queue_drain_loop(queue),
        owner="durable_queue_drain",
        name="orchestrator-durable_queue_drain",
    )
    _ = await spawn_tracked_background_task(
        coro=stale_task_recovery_loop(),
        owner="task_recovery",
        name="orchestrator-task_recovery",
    )
    _ = await spawn_tracked_background_task(
        coro=config_management.transient_failure_cleanup_loop(config_deps),
        owner="transient_failure_cleanup",
        name="orchestrator-transient_failure_cleanup",
    )
    _ = await spawn_tracked_background_task(
        coro=config_management.queue_monitor_loop(config_deps),
        owner="queue_monitor",
        name="orchestrator-queue_monitor",
    )
    return planner_worker_count, planner_worker_next_id
