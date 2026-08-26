"""SoAI - Task registry cache eviction operations [backend/core/tasks/eviction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryEvictionView
from core.tasks.task import Task

__all__ = (
    "cleanup_evicted_events",
    "evict_if_needed",
)

LOGGER_NAME = "SoAI.core.tasks.eviction"


def _task_age_key(task: Task) -> float:
    return float(task.completed_at_ms or task.updated_at_ms or task.created_at_ms)


def evict_if_needed(registry: TaskRegistryEvictionView) -> list[str]:
    logger = get_logger(LOGGER_NAME)
    if len(registry.tasks) <= registry.memory_cache_max_size:
        return []
    to_remove = len(registry.tasks) - registry.memory_cache_max_size
    evicted_terminal_ids: list[str] = []
    terminal_candidates = [
        (tid, task) for tid, task in registry.tasks.items() if task.status.is_terminal()
    ]
    terminal_candidates.sort(key=lambda entry: _task_age_key(entry[1]))
    for tid, _ in terminal_candidates:
        if to_remove <= 0:
            break
        registry.tasks.pop(tid, None)
        evicted_terminal_ids.append(tid)
        to_remove -= 1
    if to_remove <= 0:
        return evicted_terminal_ids
    active_candidates = [
        (tid, task)
        for tid, task in registry.tasks.items()
        if not task.status.is_terminal() and task.reply_queue is None
    ]
    active_candidates.sort(key=lambda entry: _task_age_key(entry[1]))
    for tid, _ in active_candidates:
        if to_remove <= 0:
            break
        registry.tasks.pop(tid, None)
        to_remove -= 1
    if to_remove > 0:
        logger.warning(
            "Task cache exceeds memory_cache_max_size by %d pinned task(s) (streaming reply queues attached).",
            to_remove,
        )
    return evicted_terminal_ids


async def cleanup_evicted_events(
    registry: TaskRegistryEvictionView,
    evicted_ids: list[str],
) -> None:
    for task_id in evicted_ids:
        await registry.ensure_completion_event(task_id, set_if_terminal=True)
    for task_id in evicted_ids:
        await registry.drop_task_lock(task_id)
