"""SoAI - Claimed backup restore write execution [backend/app/backup/restore_claimed_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.restore_journal import RestoreJournalState, transition_restore_journal
from app.backup.restore_phase_rollback import (
    handle_phase_rollback,
)
from app.backup.restore_phases import execute_restore_phase
from app.backup.restore_snapshot import (
    create_pre_restore_snapshot,
)
from app.backup.task_registry_reporting import update_progress_noncritical
from core.archives.reservations import open_write_claim

if TYPE_CHECKING:
    from app.backup.internal_protocols import RestoreTaskRunnerContext
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = ("RestoreClaimedExecutionResult", "execute_claimed_restore_writes")

OPERATION = "app.backup.restore_task_runner.run_restore_backup_task"


@dataclass(frozen=True, slots=True)
class RestoreClaimedExecutionResult:
    journal_state: RestoreJournalState
    restore_completed: bool


async def execute_claimed_restore_writes(
    *,
    context: RestoreTaskRunnerContext,
    project_root: str,
    backups_path: str,
    backup_path: str,
    backup_id: str,
    task_id: str,
    user_id: int,
    manifest: JSONDict,
    manifest_files: JSONDict,
    restore_destinations: dict[str, str],
    restore_results: list[JSONDict],
    registry: TaskRegistryProtocol,
    logger: LoggerProtocol,
    snapshot_reservation: DiskSpaceReservationLeaseProtocol,
    restore_reservation: DiskSpaceReservationLeaseProtocol,
    snapshot_required_bytes: int,
    restore_required_bytes: int,
    database_core_shutdown: bool,
) -> RestoreClaimedExecutionResult:
    await update_progress_noncritical(
        registry=registry,
        task_id=task_id,
        progress_current=1,
        log=logger,
        operation=OPERATION,
        message="Failed to update pre-restore snapshot progress.",
        status_message="Creating pre-restore snapshot",
        level="debug",
    )
    with open_write_claim(snapshot_reservation, size_bytes=snapshot_required_bytes) as claim:
        journal_state = await create_pre_restore_snapshot(
            project_root=project_root,
            backups_path=backups_path,
            manifest_files=manifest_files,
            restore_destinations=restore_destinations,
            log=logger,
        )
        if claim is not None:
            claim.commit()

    journal_state = await transition_restore_journal(
        project_root,
        expected_state=journal_state,
        phase="committing",
    )
    with open_write_claim(restore_reservation, size_bytes=restore_required_bytes) as claim:
        phase_result = await execute_restore_phase(
            backup_path=backup_path,
            manifest=manifest,
            manifest_files=manifest_files,
            restore_destinations=restore_destinations,
            config=context.config,
            runtime_dependencies=context.runtime_dependencies,
            registry=registry,
            task_id=task_id,
            user_id=user_id,
            database_core_shutdown=database_core_shutdown,
        )
        if phase_result is not None:
            restore_results.append(phase_result.result)
            if phase_result.has_errors:
                await handle_phase_rollback(
                    context=context,
                    project_root=project_root,
                    restore_results=restore_results,
                    restore_destinations=restore_destinations,
                    finalize_restored_db=database_core_shutdown,
                    backup_id=backup_id,
                    task_id=task_id,
                    user_id=user_id,
                    registry=registry,
                    progress_percent=90,
                    error_message="Restore failed; rolled back to previous state",
                )
                return RestoreClaimedExecutionResult(
                    journal_state=journal_state,
                    restore_completed=False,
                )
        if claim is not None:
            claim.commit()

    return RestoreClaimedExecutionResult(
        journal_state=journal_state,
        restore_completed=True,
    )
