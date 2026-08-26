"""SoAI - Task registry cache lookup and terminal TTL pruning [backend/core/tasks/task_registry_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.tasks.task_state_merge import merge_task_state

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.task import Task

__all__ = ("resolve_cached_task_locked",)


def resolve_cached_task_locked(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    *,
    now: float,
) -> Task | None:
    cached_active = registry.tasks.get(task_id)
    terminal_entry = registry.terminal_cache.get(task_id)
    cached_terminal: Task | None = None
    if terminal_entry is not None:
        terminal_task, cached_at = terminal_entry
        if now - cached_at < registry.terminal_cache_ttl:
            cached_terminal = terminal_task
        else:
            del registry.terminal_cache[task_id]
    if cached_active is None:
        return cached_terminal
    if cached_terminal is None:
        return cached_active
    return merge_task_state(cached=cached_terminal, incoming=cached_active)
