"""SoAI - Prompt-slot task cache lifecycle [backend/orchestrator/prompt_slot_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.orchestrator.protocols_queue import QueuePriorityViewProtocol
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task

__all__ = ("release_prompt_slot_and_update_cache",)


async def release_prompt_slot_and_update_cache(
    priority: QueuePriorityViewProtocol,
    task_registry: TaskRegistryProtocol,
    task: Task,
) -> Task:
    released_task = priority.release_prompt_slot(task)
    await task_registry.update_task_cache(released_task)
    return released_task
