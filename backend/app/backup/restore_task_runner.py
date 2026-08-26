"""SoAI - Backup restoration task orchestration [backend/app/backup/restore_task_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING

from app.backup.backup_locking import release_operations_lock
from app.backup.internal_protocols import RestoreTaskRunnerContext
from app.backup.licensing_recovery import validate_restore_licensing_pair
from app.backup.restore_claimed_execution import (
    execute_claimed_restore_writes,
)
from app.backup.restore_completion import (
    aggregate_restore_results,
    complete_committed_restore,
)
from app.backup.restore_destinations import build_restore_destinations
from app.backup.restore_disk_reservations import reserve_restore_disk_space
from app.backup.restore_journal import (
    RestoreCompletionRecord,
    transition_restore_journal,
)
from app.backup.restore_maintenance import enter_maintenance_mode
from app.backup.restore_phase_rollback import handle_cancelled_phase_rollback
from app.backup.restore_phases import shutdown_database_for_restore
from app.backup.restore_staging_cleanup import cleanup_stale_restore_staging_artifacts
from app.backup.restore_task_failures import handle_restore_task_exception
from app.backup.restore_validation import validate_and_prepare_restore
from core.backup.manifest import normalize_manifest_files_map
from core.backup.paths import (
    get_backup_relative_database_path,
    get_backup_relative_encryption_key_path,
)
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    NotFoundError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol
    from core.types.json import JSONDict

__all__ = ("run_restore_backup_task",)

LOGGER_NAME = "SoAI.app.backup.restore_task_runner"
OPERATION = "app.backup.restore_task_runner.run_restore_backup_task"


def _consume_current_task_cancellation() -> None:
    current_task = asyncio.current_task()
    if current_task is None:
        return
    for _ in range(current_task.cancelling()):
        current_task.uncancel()


async def _request_committed_restore_recovery(
    context: RestoreTaskRunnerContext,
) -> None:
    context.runtime_dependencies.request_restart(
        "backup_restore_commit_recovery_pending",
    )


async def run_restore_backup_task(
    self: RestoreTaskRunnerContext,
    task_id: str,
    backup_id: str,
    *,
    user_id: int,
    cancellation_id: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    registry = self.runtime_dependencies.task_registry
    restore_destinations: dict[str, str] | None = None
    backups_path = self.backups_path
    operations_lock = None
    project_root = ""
    database_core_shutdown = False
    maintenance_transition_started = False
    snapshot_reservation: DiskSpaceReservationLeaseProtocol | None = None
    restore_reservation: DiskSpaceReservationLeaseProtocol | None = None
    restore_results: list[JSONDict] = []
    durable_commit_completed = False

    try:
        validated_context = await validate_and_prepare_restore(
            backup_id=backup_id,
            backups_path=backups_path,
            config=self.config,
            files=self.files,
            log=logger,
        )
        operations_lock = validated_context.operations_lock
        manifest = validated_context.manifest
        backup_id = validated_context.backup_id
        backup_path = validated_context.backup_path
        snapshot_reservation, restore_reservation = reserve_restore_disk_space(
            storage_manager=self.runtime_dependencies.storage_manager,
            backups_path=backups_path,
            backup_id=backup_id,
            backup_path=backup_path,
            snapshot_required_bytes=validated_context.snapshot_required_bytes,
            restore_required_bytes=validated_context.restore_required_bytes,
        )
        raw_project_root = self.config.get("SYSTEM.PATHS.BASE")
        if not isinstance(raw_project_root, str) or not raw_project_root.strip():
            raise StateError(
                "Application base path is unavailable for licensing restore validation."
            )
        project_root = raw_project_root

        async with self.restore_lock:
            maintenance_transition_started = True
            await enter_maintenance_mode(
                runtime_dependencies=self.runtime_dependencies,
                registry=registry,
                runtime_quiescence=self.restore_runtime_quiescence,
                task_id=task_id,
                cancellation_id=cancellation_id,
            )

            restore_destinations = build_restore_destinations(self.config, self.files)
            await cleanup_stale_restore_staging_artifacts(
                backups_path=backups_path,
                restore_destinations=restore_destinations,
                log=logger,
            )
            raw_manifest_files = manifest.get("files")
            if not isinstance(raw_manifest_files, dict):
                raise ValidationError("Manifest files must be a dictionary.")
            manifest_files = normalize_manifest_files_map(raw_manifest_files)
            database_core_shutdown = any(
                relative_path in manifest_files
                for relative_path in (
                    get_backup_relative_database_path(),
                    get_backup_relative_encryption_key_path(),
                )
            )
            if database_core_shutdown:
                await shutdown_database_for_restore(
                    runtime_dependencies=self.runtime_dependencies,
                )
            await run_joined_thread_call(
                partial(
                    validate_restore_licensing_pair,
                    backup_path,
                    manifest,
                    manifest_files,
                    project_root,
                    expected_edition=self.edition,
                    live_database_path=restore_destinations.get("db_path"),
                ),
                task_name="backup-restore-licensing-pair-validation",
            )

            claimed_result = await execute_claimed_restore_writes(
                context=self,
                project_root=project_root,
                backups_path=backups_path,
                backup_path=backup_path,
                backup_id=backup_id,
                task_id=task_id,
                user_id=user_id,
                manifest=manifest,
                manifest_files=manifest_files,
                restore_destinations=restore_destinations,
                restore_results=restore_results,
                registry=registry,
                logger=logger,
                snapshot_reservation=snapshot_reservation,
                restore_reservation=restore_reservation,
                snapshot_required_bytes=validated_context.snapshot_required_bytes,
                restore_required_bytes=validated_context.restore_required_bytes,
                database_core_shutdown=database_core_shutdown,
            )
            journal_state = claimed_result.journal_state
            if not claimed_result.restore_completed:
                return
            summary = aggregate_restore_results(restore_results, backup_id)
            if not summary.success:
                raise StateError("Restore writes cannot commit with recorded errors.")
            database_path = restore_destinations.get("db_path")
            if not isinstance(database_path, str) or not database_path.strip():
                raise StateError("Restore database destination is unavailable.")
            completion = RestoreCompletionRecord(
                task_id=task_id,
                user_id=user_id,
                backup_id=backup_id,
                cancellation_id=cancellation_id,
                database_path=database_path,
                database_was_shutdown=database_core_shutdown,
                completed_at_ms=epoch_ms(),
                result=summary.combined_result,
            )

            journal_state = await uncancel_then_cleanup(
                transition_restore_journal(
                    project_root,
                    expected_state=journal_state,
                    phase="committed",
                    completion=completion,
                )
            )
            _consume_current_task_cancellation()
            durable_commit_completed = True
            await uncancel_then_cleanup(
                complete_committed_restore(
                    project_root=project_root,
                    journal_state=journal_state,
                    restore_destinations=restore_destinations,
                    runtime_dependencies=self.runtime_dependencies,
                    registry=registry,
                    log=logger,
                )
            )
            _consume_current_task_cancellation()
    except asyncio.CancelledError:
        if durable_commit_completed:
            await uncancel_then_cleanup(_request_committed_restore_recovery(self))
        elif maintenance_transition_started and project_root:
            await uncancel_then_cleanup(
                handle_cancelled_phase_rollback(
                    context=self,
                    project_root=project_root,
                )
            )
        raise
    except (
        NotFoundError,
        ValidationError,
        SecurityError,
        StateError,
        InsufficientDiskSpaceError,
    ) as exception:
        if durable_commit_completed:
            log_exception(
                logger,
                exception,
                message="Committed restore finalization will resume during startup.",
                operation=OPERATION,
                details={"backup_id": backup_id, "task_id": task_id},
                level="warning",
            )
            await _request_committed_restore_recovery(self)
            return
        await handle_restore_task_exception(
            context=self,
            task_id=task_id,
            backup_id=backup_id,
            user_id=user_id,
            registry=registry,
            project_root=project_root,
            maintenance_transition_started=maintenance_transition_started,
            restore_destinations=restore_destinations,
            restore_results=restore_results,
            database_core_shutdown=database_core_shutdown,
            exception=exception,
        )
        return
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Restore task runner failed.",
            operation=OPERATION,
            details={"backup_id": backup_id, "task_id": task_id},
            level="warning",
        )
        if durable_commit_completed:
            await _request_committed_restore_recovery(self)
            return
        await handle_restore_task_exception(
            context=self,
            task_id=task_id,
            backup_id=backup_id,
            user_id=user_id,
            registry=registry,
            project_root=project_root,
            maintenance_transition_started=maintenance_transition_started,
            restore_destinations=restore_destinations,
            restore_results=restore_results,
            database_core_shutdown=database_core_shutdown,
            exception=exception,
        )
    finally:
        if restore_reservation is not None:
            restore_reservation.release()
        if snapshot_reservation is not None:
            snapshot_reservation.release()
        if operations_lock is not None:
            await uncancel_then_cleanup(release_operations_lock(operations_lock, log=logger))
        if durable_commit_completed:
            _consume_current_task_cancellation()
