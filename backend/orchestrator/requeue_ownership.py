"""SoAI - Orchestrator requeue ownership release [backend/orchestrator/requeue_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.orchestrator.protocols_queue import QueueCycleType
from orchestrator.prompt_slot_lifecycle import release_prompt_slot_and_update_cache

if TYPE_CHECKING:
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task

__all__ = (
    "close_task_queue_cycles",
    "release_task_execution_ownership",
)


async def close_task_queue_cycles(
    queue: OrchestratorQueueProtocol,
    task: Task,
    *,
    close_priority_cycle: bool,
    close_plugin_cycle: bool,
) -> None:
    if close_priority_cycle:
        await queue.cycles.close_cycle(task, QueueCycleType.PRIORITY, for_requeue=True)
    if close_plugin_cycle:
        await queue.cycles.close_cycle(task, QueueCycleType.PLUGIN, for_requeue=True)


async def release_task_execution_ownership(
    queue: OrchestratorQueueProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
    *,
    close_priority_cycle: bool,
    close_plugin_cycle: bool,
) -> Task:
    await close_task_queue_cycles(
        queue,
        task,
        close_priority_cycle=close_priority_cycle,
        close_plugin_cycle=close_plugin_cycle,
    )
    return await release_prompt_slot_and_update_cache(queue.priority, task_registry, task)
