"""SoAI - Task registry lock acquisition with optional lock dropping [backend/core/tasks/task_lock_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.di.validation import require_dependencies
from core.tasks.protocols import TaskLockView, TaskRegistryLifecycleView

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from core.tasks.task import Task

__all__ = (
    "TaskLockControl",
    "load_task_with_drop_control",
    "task_lock_control",
)


@dataclass(slots=True)
class TaskLockControl:
    lock_wrapper: TaskLockView
    drop_after_exit: bool = False

    def __post_init__(self) -> None:
        require_dependencies(owner="TaskLockControl", lock_wrapper=self.lock_wrapper)

    def request_drop_after_exit(self) -> None:
        self.drop_after_exit = True


@asynccontextmanager
async def task_lock_control(
    registry: TaskRegistryLifecycleView,
    task_id: str,
) -> AsyncGenerator[TaskLockControl]:
    lock_wrapper = registry.get_task_lock(task_id)
    control = TaskLockControl(lock_wrapper=lock_wrapper)
    try:
        async with lock_wrapper.lock:
            yield control
    finally:
        if control.drop_after_exit:
            await uncancel_then_cleanup(registry.drop_task_lock(task_id))


async def load_task_with_drop_control(
    registry: TaskRegistryLifecycleView,
    lock_control: TaskLockControl,
    task_id: str,
) -> Task | None:
    task = await registry.get(task_id)
    if task is None:
        lock_control.request_drop_after_exit()
        return None
    if task.status.is_terminal():
        lock_control.request_drop_after_exit()
    return task
