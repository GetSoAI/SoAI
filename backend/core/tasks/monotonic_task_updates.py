"""SoAI - Monotonic task state updates [backend/core/tasks/monotonic_task_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import dataclasses

from core.tasks.enums import TaskStatus
from core.tasks.progress_monotonicity import MonotonicProgressUpdate
from core.tasks.task import Task

__all__ = ("apply_monotonic_task_update",)


def apply_monotonic_task_update(
    *,
    task: Task,
    monotonic_update: MonotonicProgressUpdate,
    updated_at_ms: int,
    status: TaskStatus | None,
    progress_total: int | None,
) -> Task:
    resolved_status = status if status is not None else task.status
    resolved_progress_total = progress_total if progress_total is not None else task.progress_total
    return dataclasses.replace(
        task,
        status=resolved_status,
        updated_at_ms=updated_at_ms,
        update_counter=task.update_counter + 1,
        status_message=(
            monotonic_update.status_message
            if monotonic_update.status_message is not None
            else task.status_message
        ),
        progress_current=(
            monotonic_update.progress_current
            if monotonic_update.progress_current is not None
            else task.progress_current
        ),
        progress_total=(
            resolved_progress_total if resolved_progress_total is not None else task.progress_total
        ),
        progress_details=(
            monotonic_update.progress_details
            if monotonic_update.progress_details is not None
            else task.progress_details
        ),
    )
