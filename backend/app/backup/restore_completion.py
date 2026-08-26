"""SoAI - Backup restore completion and finalization [backend/app/backup/restore_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.copy_no_symlinks.permissions import ensure_backup_directory_permissions
from app.backup.restore_committed_finalization import finalize_committed_restore_record
from app.backup.restore_journal import (
    RestoreJournalState,
    remove_restore_journal,
)
from app.backup.restore_snapshot import cleanup_pre_restore_snapshot
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir
from core.logging.protocols import LoggerProtocol
from core.runtime.platform import get_runtime_platform

if TYPE_CHECKING:
    from app.backup.internal_protocols import BackupRuntimeDependenciesProtocol
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict

__all__ = (
    "RestoreCompletionSummary",
    "aggregate_restore_results",
    "complete_committed_restore",
    "ensure_restored_directory_permissions",
)

OPERATION_PUBLISH = "application_restore.run_restore_backup_task.publish"


@dataclass(frozen=True, slots=True)
class RestoreCompletionSummary:
    restored_files: list[str]
    restore_errors: list[JSONDict]
    success: bool
    combined_result: JSONDict


def aggregate_restore_results(
    restore_results: list[JSONDict],
    backup_id: str,
) -> RestoreCompletionSummary:
    restored_files: list[str] = []
    restore_errors: list[JSONDict] = []
    for restore_item in restore_results:
        restored_items = restore_item.get("files_restored")
        if isinstance(restored_items, list):
            restored_files.extend(item for item in restored_items if isinstance(item, str))
        error_items = restore_item.get("errors")
        if isinstance(error_items, list):
            restore_errors.extend(dict(item) for item in error_items if isinstance(item, dict))
    success = not restore_errors
    combined_result: JSONDict = {
        "backup_id": backup_id,
        "files_restored": restored_files,
        "errors": restore_errors,
        "success": success,
        "rolled_back": False,
    }
    return RestoreCompletionSummary(
        restored_files=restored_files,
        restore_errors=restore_errors,
        success=success,
        combined_result=combined_result,
    )


async def complete_committed_restore(
    *,
    project_root: str,
    journal_state: RestoreJournalState,
    restore_destinations: dict[str, str],
    runtime_dependencies: BackupRuntimeDependenciesProtocol,
    registry: TaskRegistryProtocol,
    log: LoggerProtocol,
) -> None:
    completion = journal_state.completion
    if journal_state.phase != "committed" or completion is None:
        raise StateError("Restore completion requires a committed journal record.")
    await finalize_committed_restore_record(
        completion,
        registry=registry,
    )
    await ensure_restored_directory_permissions(restore_destinations, log=log)
    await cleanup_pre_restore_snapshot(snapshot_path=journal_state.snapshot_path, log=log)
    await remove_restore_journal(project_root, expected_state=journal_state)
    runtime_dependencies.request_restart("backup_restore_complete")


async def ensure_restored_directory_permissions(
    restore_destinations: dict[str, str],
    *,
    log: LoggerProtocol,
) -> None:
    runtime_platform = get_runtime_platform()
    for target_path_key in ("files_storage_path", "logs_path", "wallpaper_path"):
        target_path = restore_destinations.get(target_path_key)
        if not target_path or not await async_isdir(target_path):
            continue
        try:
            await ensure_backup_directory_permissions(
                target_path,
                is_windows=runtime_platform.is_windows,
                force_walk=True,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Failed to normalize restored directory permissions.",
                operation=OPERATION_PUBLISH,
                details={"target_path_key": target_path_key, "target_path": target_path},
                level="warning",
            )
