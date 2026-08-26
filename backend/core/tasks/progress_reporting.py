"""SoAI - Task progress reporting helpers that do not change task status [backend/core/tasks/progress_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.tasks.monotonic_task_updates import apply_monotonic_task_update
from core.tasks.progress_details import serialize_progress_details
from core.tasks.progress_events import emit_task_progress_event_for_task
from core.tasks.progress_monotonicity import resolve_monotonic_progress_update
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task import Task
from core.tasks.task_lock_control import task_lock_control
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("report_progress_without_status_change",)

LOGGER_NAME = "SoAI.core.tasks.progress_reporting"


async def report_progress_without_status_change(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    progress_current: int,
    *,
    status_message: str | None = None,
    details: JSONValue | None = None,
    percent_override: int | None = None,
) -> Task | None:
    logger = get_logger(LOGGER_NAME)
    details_str = serialize_progress_details(details)

    async with task_lock_control(registry, task_id):
        task = await registry.get(task_id)
        if task is None:
            return None
        if task.status.is_terminal():
            return None
        monotonic_update = resolve_monotonic_progress_update(
            task,
            progress_current=progress_current,
            status_message=status_message,
            progress_details=details_str or None,
            percent_override=percent_override,
        )
        db_success = await registry.database_tasks.update_unified_task_status(
            task_id=task_id,
            status=task.status.value,
            status_message=monotonic_update.status_message,
            progress_current=monotonic_update.progress_current,
            progress_total=task.progress_total,
            progress_details=monotonic_update.progress_details,
        )
        if not db_success:
            refreshed = await registry.get(task_id, force_refresh=True)
            if refreshed and refreshed.status.is_terminal():
                return None
            logger.warning(
                "Failed to persist progress update for task %s (DB row may be missing/expired or already terminal)",
                task_id,
            )
            return None
        task = apply_monotonic_task_update(
            task=task,
            monotonic_update=monotonic_update,
            updated_at_ms=epoch_ms(),
            status=None,
            progress_total=None,
        )
        await registry.update_task_cache(task)
        await emit_task_progress_event_for_task(
            registry,
            task=task,
            progress_current=(
                task.progress_current if task.progress_current is not None else progress_current
            ),
            status_message=task.status_message,
            details=task.progress_details if monotonic_update.stale else details,
            percent_override=monotonic_update.percent_override,
            logger=logger,
        )
    return task
