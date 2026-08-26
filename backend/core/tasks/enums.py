"""SoAI - Task status and type enums [backend/core/tasks/enums.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

__all__ = ("TASK_STATUS_SQL_VALUES", "TaskStatus")


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    AWAITING_SCHEDULER = "awaiting_scheduler"
    DEDUPED = "deduped"
    DISPATCHED = "dispatched"
    WORKING = "working"
    PROCESSING = "processing"
    INPUT_REQUIRED = "input_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)

    def can_transition_to(self, new_status: TaskStatus) -> bool:
        if self.is_terminal():
            return False
        if self == new_status:
            return True
        terminals = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        valid_transitions: dict[TaskStatus, set[TaskStatus]] = {
            TaskStatus.PENDING: {
                TaskStatus.QUEUED,
                TaskStatus.WORKING,
                TaskStatus.INPUT_REQUIRED,
                *terminals,
            },
            TaskStatus.QUEUED: {
                TaskStatus.AWAITING_SCHEDULER,
                TaskStatus.DEDUPED,
                TaskStatus.DISPATCHED,
                TaskStatus.PROCESSING,
                TaskStatus.WORKING,
                *terminals,
            },
            TaskStatus.AWAITING_SCHEDULER: {
                TaskStatus.QUEUED,
                TaskStatus.DEDUPED,
                TaskStatus.DISPATCHED,
                TaskStatus.PROCESSING,
                *terminals,
            },
            TaskStatus.DEDUPED: {TaskStatus.QUEUED, *terminals},
            TaskStatus.DISPATCHED: {
                TaskStatus.QUEUED,
                TaskStatus.PROCESSING,
                *terminals,
            },
            TaskStatus.WORKING: {TaskStatus.INPUT_REQUIRED, *terminals},
            TaskStatus.PROCESSING: {TaskStatus.QUEUED, *terminals},
            TaskStatus.INPUT_REQUIRED: {TaskStatus.WORKING, *terminals},
        }
        return new_status in valid_transitions.get(self, set())


TASK_STATUS_SQL_VALUES: tuple[str, ...] = (
    "pending",
    "queued",
    "awaiting_scheduler",
    "deduped",
    "dispatched",
    "working",
    "processing",
    "input_required",
    "completed",
    "failed",
    "cancelled",
)
