"""SoAI - Task status and progress transitions [backend/core/tasks/status_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.awaitable_flags import resolve_bool_flag
from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.progress.transfer_details import resolve_transfer_details_payload
from core.tasks.enums import TaskStatus
from core.tasks.monotonic_task_updates import apply_monotonic_task_update
from core.tasks.notifications import notify_status_changed
from core.tasks.progress_details import serialize_progress_details
from core.tasks.progress_events import (
    emit_task_progress_event_for_task_with_details_str,
)
from core.tasks.progress_monotonicity import resolve_monotonic_progress_update
from core.tasks.protocols import TaskRegistryLifecycleView
from core.tasks.task import Task
from core.tasks.task_lock_control import task_lock_control
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "update_progress",
    "update_status",
)

LOGGER_NAME = "SoAI.core.tasks.status_transitions"


async def update_status(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    new_status: TaskStatus,
    *,
    status_message: str | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    progress_details: str | None = None,
    percent_override: int | None = None,
    infer_working_status: bool = False,
    emit_progress_event: bool = False,
) -> Task | None:
    logger = get_logger(LOGGER_NAME)
    if not infer_working_status and new_status.is_terminal():
        raise ValidationError(
            f"Cannot use update_status() for terminal state '{new_status.value}'. Use finalize() or cancel() instead.",
        )
    async with task_lock_control(registry, task_id):
        task = await registry.get(task_id)
        if task is None:
            return None
        if await resolve_bool_flag(task.status.is_terminal()):
            return None
        if infer_working_status:
            if task.status == TaskStatus.INPUT_REQUIRED:
                new_status = TaskStatus.INPUT_REQUIRED
            elif task.status.can_transition_to(TaskStatus.WORKING):
                new_status = TaskStatus.WORKING
            else:
                new_status = task.status
        old_status = task.status
        if not old_status.can_transition_to(new_status):
            raise ValidationError(
                f"Invalid status transition: '{old_status.value}' -> '{new_status.value}'",
            )
        monotonic_update = resolve_monotonic_progress_update(
            task,
            progress_current=progress_current,
            progress_total=progress_total,
            status_message=status_message,
            progress_details=progress_details,
            percent_override=percent_override,
        )
        resolved_progress_total = task.progress_total if monotonic_update.stale else progress_total
        db_success = await registry.database_tasks.update_unified_task_status(
            task_id=task_id,
            status=new_status.value,
            status_message=monotonic_update.status_message,
            progress_current=monotonic_update.progress_current,
            progress_total=resolved_progress_total,
            progress_details=monotonic_update.progress_details,
        )
        if not db_success:
            refreshed = await registry.get(task_id, force_refresh=True)
            if refreshed and refreshed.status.is_terminal():
                return None
            logger.warning(
                "Failed to persist status update for task %s (DB row may be missing/expired or already terminal)",
                task_id,
            )
            return None
        task = apply_monotonic_task_update(
            task=task,
            monotonic_update=monotonic_update,
            updated_at_ms=epoch_ms(),
            status=new_status,
            progress_total=resolved_progress_total,
        )
        await registry.update_task_cache(task)
        registry.try_log_terminal_progress(task, old_status=old_status)
        await notify_status_changed(registry.event_bus, task, old_status)
        if old_status != new_status:
            logger.debug(
                "Updated task %s: %s -> %s",
                task_id,
                old_status.value,
                new_status.value,
            )
        if emit_progress_event:
            if monotonic_update.stale:
                event_details_str = task.progress_details or ""
            else:
                event_details_str = progress_details or ""
            await emit_task_progress_event_for_task_with_details_str(
                registry,
                task=task,
                progress_current=(
                    task.progress_current
                    if task.progress_current is not None
                    else progress_current or 0
                ),
                status_message=task.status_message,
                details_str=event_details_str,
                percent_override=monotonic_update.percent_override,
                logger=logger,
            )
        return task


async def update_progress(
    registry: TaskRegistryLifecycleView,
    task_id: str,
    progress_current: int,
    *,
    status_message: str | None = None,
    details: JSONValue | None = None,
    percent_override: int | None = None,
) -> Task | None:
    details_payload = resolve_transfer_details_payload(details)
    details_str = serialize_progress_details(details_payload)
    task = await update_status(
        registry,
        task_id,
        TaskStatus.WORKING,
        progress_current=progress_current,
        status_message=status_message,
        progress_details=details_str or None,
        percent_override=percent_override,
        infer_working_status=True,
        emit_progress_event=True,
    )
    return task
