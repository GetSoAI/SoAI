"""SoAI - Monotonic task progress resolution [backend/core/tasks/progress_monotonicity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.progress.percent import clamp_percent
from core.tasks.progress_events import compute_progress_percent
from core.tasks.task import Task

__all__ = (
    "MonotonicProgressUpdate",
    "resolve_monotonic_progress_update",
)


@dataclass(frozen=True, slots=True)
class MonotonicProgressUpdate:
    progress_current: int | None
    status_message: str | None
    progress_details: str | None
    percent_override: int | None
    stale: bool


def clamp_percent_override_to_existing(
    *,
    task: Task,
    percent_override: int | None,
) -> int | None:
    if percent_override is None or task.progress_current is None:
        return percent_override
    existing_percent = compute_progress_percent(task.progress_current, task.progress_total, None)
    return max(percent_override, existing_percent)


def _compute_existing_percent(task: Task) -> int | None:
    if task.progress_current is None:
        return None
    return compute_progress_percent(task.progress_current, task.progress_total, None)


def _compute_incoming_percent(
    task: Task,
    *,
    progress_current: int | None,
    progress_total: int | None,
    percent_override: int | None,
) -> int | None:
    if percent_override is not None:
        return clamp_percent(percent_override)
    if progress_current is None:
        return None
    resolved_total = progress_total if progress_total is not None else task.progress_total
    return compute_progress_percent(progress_current, resolved_total, None)


def resolve_monotonic_progress_update(
    task: Task,
    *,
    progress_current: int | None,
    status_message: str | None,
    progress_details: str | None,
    progress_total: int | None = None,
    percent_override: int | None = None,
) -> MonotonicProgressUpdate:
    existing_progress = task.progress_current
    existing_percent = _compute_existing_percent(task)
    incoming_percent = _compute_incoming_percent(
        task,
        progress_current=progress_current,
        progress_total=progress_total,
        percent_override=percent_override,
    )
    effective_percent_override = clamp_percent_override_to_existing(
        task=task,
        percent_override=percent_override,
    )
    if existing_percent is not None and incoming_percent is not None:
        if incoming_percent < existing_percent:
            return MonotonicProgressUpdate(
                progress_current=existing_progress,
                status_message=task.status_message,
                progress_details=task.progress_details,
                percent_override=effective_percent_override,
                stale=True,
            )
    resolved_progress_current = progress_current
    if progress_current is not None and existing_progress is not None:
        resolved_progress_current = max(progress_current, existing_progress)
    return MonotonicProgressUpdate(
        progress_current=resolved_progress_current,
        status_message=status_message,
        progress_details=progress_details,
        percent_override=effective_percent_override,
        stale=False,
    )
