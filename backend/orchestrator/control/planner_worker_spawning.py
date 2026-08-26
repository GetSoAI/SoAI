"""SoAI - Planner worker spawn helpers [backend/orchestrator/control/planner_worker_spawning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.orchestrator.queue_decisions import QueueDecision
from core.tasks.protocols import SpawnTrackedBackgroundTaskCallable
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.queueing.worker_processing import worker_loop

__all__ = ("spawn_planner_worker",)


async def spawn_planner_worker(
    *,
    spawn_background_task: SpawnTrackedBackgroundTaskCallable,
    queue: QueueServiceView,
    worker_id: int,
    decision_handler: Callable[[QueueDecision], Awaitable[None]],
) -> None:
    _ = await spawn_background_task(
        coro=worker_loop(
            queue=queue,
            worker_id=worker_id,
            decision_handler=decision_handler,
        ),
        owner="planner_worker",
        metadata={"worker_id": worker_id},
        name=f"orchestrator-planner-{worker_id}",
    )
