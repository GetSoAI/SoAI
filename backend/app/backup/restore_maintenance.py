"""SoAI - Backup restore maintenance mode operations [backend/app/backup/restore_maintenance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.backup.task_event_publishing import publish_event_noncritical
from app.backup.task_registry_reporting import update_progress_noncritical
from core.events.types_system import SystemQuiesceEvent
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC

if TYPE_CHECKING:
    from app.backup.internal_protocols import (
        BackupRuntimeDependenciesProtocol,
        RestoreRuntimeQuiescenceProtocol,
    )
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("enter_maintenance_mode",)

LOGGER_NAME = "SoAI.app.backup.restore_maintenance"


async def enter_maintenance_mode(
    *,
    runtime_dependencies: BackupRuntimeDependenciesProtocol,
    registry: TaskRegistryProtocol,
    runtime_quiescence: RestoreRuntimeQuiescenceProtocol,
    task_id: str,
    cancellation_id: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    await update_progress_noncritical(
        registry=registry,
        task_id=task_id,
        progress_current=0,
        log=logger,
        operation="app.backup.restore_maintenance.progress",
        message="Failed to update restore maintenance progress.",
        status_message="Entering maintenance mode",
        level="debug",
    )
    runtime_dependencies.orchestrator_control.set_quiescent(True)
    await publish_event_noncritical(
        event_bus=runtime_dependencies.event_bus,
        event=SystemQuiesceEvent(reason="restore_requested"),
        log=logger,
        operation="app.backup.restore_maintenance.publish",
        message="Failed to publish restore quiesce event.",
        details={"task_id": str(task_id)},
        level="debug",
    )
    await runtime_dependencies.cancellation_coordinator.cancel_all_scopes(
        "Backup restore requested",
        include_internal=False,
        exclude_cancellation_ids=(str(cancellation_id),),
        wait_for_release_timeout=CONTROL_TIMEOUT_SEC,
    )
    await runtime_quiescence.shutdown()
