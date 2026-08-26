"""SoAI - Runtime task state after terminal persistence [backend/orchestrator/execution/outcome_task_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import replace

from core.errors.exceptions import StateError
from core.tasks.task import Task

__all__ = ("apply_terminal_persistence_to_runtime_task",)


def apply_terminal_persistence_to_runtime_task(task: Task, terminal_task: Task) -> Task:
    if task.task_id != terminal_task.task_id:
        raise StateError("Terminal task identity does not match runtime task.")
    if not terminal_task.status.is_terminal():
        raise StateError("Persisted task state is not terminal.")
    return replace(
        task,
        status=terminal_task.status,
        updated_at_ms=terminal_task.updated_at_ms,
        completed_at_ms=terminal_task.completed_at_ms,
        progress_current=terminal_task.progress_current,
        progress_total=terminal_task.progress_total,
        status_message=terminal_task.status_message,
        result=terminal_task.result,
        error_code=terminal_task.error_code,
        error_message=terminal_task.error_message,
        cancellation_requested_at_ms=terminal_task.cancellation_requested_at_ms,
        update_counter=max(task.update_counter, terminal_task.update_counter),
    )
