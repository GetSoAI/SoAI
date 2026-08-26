"""SoAI - Planner worker scaling operations [backend/orchestrator/control/planner_workers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.orchestrator.queue_decisions import QueueDecision
from core.tasks.protocols import SpawnTrackedBackgroundTaskCallable
from orchestrator.control.planner_worker_spawning import spawn_planner_worker
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("apply_planner_worker_config",)

LOGGER_NAME = "SoAI.orchestrator.control.planner_workers"


async def apply_planner_worker_config(
    *,
    desired_workers: int,
    current_worker_count: int,
    next_worker_id: int,
    queue: QueueServiceView,
    decision_handler: Callable[[QueueDecision], Awaitable[None]],
    spawn_background_task: SpawnTrackedBackgroundTaskCallable,
) -> tuple[int, int, int]:
    logger = get_logger(LOGGER_NAME)
    resolved_desired = int(desired_workers)
    if resolved_desired < 1:
        raise ValidationError("NUM_PLANNER_WORKERS must be >= 1.")
    if current_worker_count <= 0:
        return (resolved_desired, 0, next_worker_id)
    if resolved_desired < current_worker_count:
        logger.warning(
            "Planner worker count decreased from %s to %s; change will apply on restart.",
            current_worker_count,
            resolved_desired,
        )
        return (current_worker_count, 0, next_worker_id)
    if resolved_desired == current_worker_count:
        return (current_worker_count, 0, next_worker_id)
    additional = resolved_desired - current_worker_count
    updated_next_worker_id = next_worker_id
    for _ in range(additional):
        worker_id = updated_next_worker_id
        updated_next_worker_id += 1
        await spawn_planner_worker(
            spawn_background_task=spawn_background_task,
            queue=queue,
            worker_id=worker_id,
            decision_handler=decision_handler,
        )
    return (resolved_desired, additional, updated_next_worker_id)
