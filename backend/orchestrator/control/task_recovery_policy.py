"""SoAI - Orchestrated task recovery policy [backend/orchestrator/control/task_recovery_policy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tasks.task import Task

__all__ = (
    "is_stale_orphan_recoverable",
    "is_startup_orphan_recoverable",
    "resolve_stale_recovery_interval_seconds",
)

MIN_STALE_RECOVERY_INTERVAL_SECONDS = 30.0
MAX_STALE_RECOVERY_INTERVAL_SECONDS = 60.0


def resolve_stale_recovery_interval_seconds(stuck_task_timeout_ms: int) -> float:
    timeout_ms = max(0, int(stuck_task_timeout_ms))
    interval_seconds = max(
        MIN_STALE_RECOVERY_INTERVAL_SECONDS,
        float(timeout_ms) / 2000.0 if timeout_ms > 0 else MIN_STALE_RECOVERY_INTERVAL_SECONDS,
    )
    return min(interval_seconds, MAX_STALE_RECOVERY_INTERVAL_SECONDS)


def is_startup_orphan_recoverable(task: Task, *, started_at_epoch_ms: int) -> bool:
    return task.updated_at_ms < started_at_epoch_ms


def is_stale_orphan_recoverable(
    task: Task,
    *,
    stuck_task_timeout_ms: int,
    current_epoch_ms: int,
) -> bool:
    timeout_ms = max(0, int(stuck_task_timeout_ms))
    if timeout_ms <= 0:
        return False
    cutoff_epoch_ms = current_epoch_ms - timeout_ms
    return task.updated_at_ms <= cutoff_epoch_ms
