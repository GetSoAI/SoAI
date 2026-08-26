"""SoAI - Backup task item progress publication and registry updates [backend/app/backup/task_item_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.task_event_publishing import publish_event_noncritical
from app.backup.task_registry_reporting import update_progress_noncritical
from core.events.types_tasks import TaskProgressEvent

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryLifecycleView

__all__ = ("report_task_item_progress",)


async def report_task_item_progress(
    *,
    event_bus: EventBusProtocol,
    registry: TaskRegistryLifecycleView | None,
    task_id: str,
    user_id: int,
    percent: int,
    rel_path: str,
    event_message: str,
    status_message: str,
    log: LoggerProtocol,
    publish_operation: str,
    publish_failure_message: str,
    publish_details: dict[str, str],
    progress_operation: str,
    progress_failure_message: str,
    progress_level: str = "debug",
) -> None:
    await publish_event_noncritical(
        event_bus=event_bus,
        event=TaskProgressEvent(
            percent=percent,
            message=event_message,
            details=rel_path,
            task_id=task_id,
            user_id=user_id,
        ),
        log=log,
        operation=publish_operation,
        message=publish_failure_message,
        details=publish_details,
        level=progress_level,
    )
    if registry is None:
        return
    await update_progress_noncritical(
        registry=registry,
        task_id=task_id,
        progress_current=percent,
        log=log,
        operation=progress_operation,
        message=progress_failure_message,
        status_message=status_message,
        level=progress_level,
    )
