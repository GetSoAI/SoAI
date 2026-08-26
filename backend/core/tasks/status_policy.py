"""SoAI - Task status grouping policy [backend/core/tasks/status_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.enums import TaskStatus

__all__ = (
    "ACTIVE_TASK_STATUS_VALUES",
    "RUNNING_TASK_STATUS_VALUES",
    "TERMINAL_TASK_STATUS_VALUES",
    "active_task_status_placeholders",
    "running_task_status_placeholders",
    "task_status_placeholders",
    "terminal_task_status_placeholders",
)

TERMINAL_TASK_STATUS_VALUES: tuple[str, ...] = (
    TaskStatus.COMPLETED.value,
    TaskStatus.FAILED.value,
    TaskStatus.CANCELLED.value,
)
ACTIVE_TASK_STATUS_VALUES: tuple[str, ...] = (
    TaskStatus.PENDING.value,
    TaskStatus.QUEUED.value,
    TaskStatus.AWAITING_SCHEDULER.value,
    TaskStatus.DEDUPED.value,
    TaskStatus.DISPATCHED.value,
    TaskStatus.WORKING.value,
    TaskStatus.PROCESSING.value,
    TaskStatus.INPUT_REQUIRED.value,
)
RUNNING_TASK_STATUS_VALUES: tuple[str, ...] = (
    TaskStatus.DISPATCHED.value,
    TaskStatus.WORKING.value,
    TaskStatus.PROCESSING.value,
    TaskStatus.INPUT_REQUIRED.value,
)


def task_status_placeholders(values: tuple[str, ...]) -> str:
    return ", ".join(("?",) * len(values))


def active_task_status_placeholders() -> str:
    return task_status_placeholders(ACTIVE_TASK_STATUS_VALUES)


def running_task_status_placeholders() -> str:
    return task_status_placeholders(RUNNING_TASK_STATUS_VALUES)


def terminal_task_status_placeholders() -> str:
    return task_status_placeholders(TERMINAL_TASK_STATUS_VALUES)
