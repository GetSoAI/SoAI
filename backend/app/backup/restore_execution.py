"""SoAI - Backup restore execution with timeout and validation [backend/app/backup/restore_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.restore_destinations import resolve_restore_destination
from app.backup.restore_staging import (
    StagedRestorePaths,
    allocate_staging_paths,
    cleanup_staging_path,
    commit_staged_item,
    stage_restore_item,
    verify_staged_item,
)
from app.backup.task_item_progress import report_task_item_progress
from app.backup.task_registry_reporting import update_status_noncritical
from app.backup.validated_manifest_entries import (
    ValidatedManifestEntry,
    build_validated_manifest_entries,
)
from core.concurrency.deadlines import deadline_after
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_finalization import cancel_and_await_task
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.filesystem.async_queries import async_makedirs, async_path_exists
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.protocols import TaskRegistryProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("restore_backup_internal",)

LOGGER_NAME = "SoAI.app.backup.restore_execution"
OPERATION = "app.backup.restore_execution.restore_item"
OPERATION_PUBLISH = "app.backup.restore_execution.publish_event"
OPERATION_PROGRESS = "app.backup.restore_execution.progress"


@dataclass(frozen=True, slots=True)
class _PreparedRestore:
    rel_path: str
    staged_paths: StagedRestorePaths
    is_directory: bool


async def restore_backup_internal(
    *,
    backup_path: str,
    manifest: JSONDict,
    task_id: str,
    user_id: int,
    update_task_registry: bool,
    restore_destinations: dict[str, str],
    copy_timeout_seconds: float,
    progress_interval_seconds: float,
    task_registry: TaskRegistryProtocol,
    event_bus: EventBusProtocol,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    files_restored: list[str] = []
    errors: list[JSONDict] = []
    result: JSONDict = {
        "backup_id": manifest.get("backup_id"),
        "files_restored": files_restored,
        "errors": errors,
        "success": False,
    }
    registry: TaskRegistryProtocol | None = task_registry if update_task_registry else None
    validated_entries = build_validated_manifest_entries(manifest.get("files"))
    total = len(validated_entries)
    prepared: list[_PreparedRestore] = []
    failure_path = "restore"
    cleanup_required = True
    try:
        for entry in validated_entries:
            failure_path = entry.rel_path
            staged = await _stage_verified_entry(
                entry=entry,
                backup_path=backup_path,
                restore_destinations=restore_destinations,
                copy_timeout_seconds=copy_timeout_seconds,
                progress_interval_seconds=progress_interval_seconds,
                registry=registry,
                task_id=task_id,
            )
            prepared.append(staged)
        for index, staged in enumerate(prepared, start=1):
            failure_path = staged.rel_path
            await commit_staged_item(
                staged.staged_paths,
                is_directory=staged.is_directory,
            )
            files_restored.append(staged.rel_path)
            await _report_restored_item(
                event_bus=event_bus,
                registry=registry,
                task_id=task_id,
                user_id=user_id,
                rel_path=staged.rel_path,
                index=index,
                total=total,
            )
        cleanup_required = False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Backup restore failed for item (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        errors.append(
            {
                "path": failure_path,
                "error": project_public_exception(exception).message,
            }
        )
    finally:
        if cleanup_required:
            await _cleanup_prepared(prepared, logger=logger)
    result["success"] = not errors
    return result


async def _stage_verified_entry(
    *,
    entry: ValidatedManifestEntry,
    backup_path: str,
    restore_destinations: dict[str, str],
    copy_timeout_seconds: float,
    progress_interval_seconds: float,
    registry: TaskRegistryProtocol | None,
    task_id: str,
) -> _PreparedRestore:
    rel_path = entry.rel_path
    source_item_path = os.path.join(backup_path, rel_path)
    if not await async_path_exists(source_item_path):
        raise StateError(
            f"Backup is missing required item: {rel_path}",
            details={"path": rel_path},
        )
    destination_item_path = resolve_restore_destination(
        rel_path,
        restore_destinations=restore_destinations,
    )
    is_directory_target = entry.entry_type == "directory"
    destination_directory = os.path.dirname(destination_item_path)
    if destination_directory:
        await async_makedirs(destination_directory, mode=0o700, exist_ok=True)
    staged_paths = allocate_staging_paths(
        destination_item_path,
        is_directory=is_directory_target,
    )
    deadline_monotonic: float | None = None
    if copy_timeout_seconds and copy_timeout_seconds > 0:
        deadline_monotonic = deadline_after(copy_timeout_seconds).deadline_monotonic
    stage_task = create_ephemeral_task(
        stage_restore_item(
            source_path=source_item_path,
            staged_paths=staged_paths,
            is_directory=is_directory_target,
            deadline_monotonic=deadline_monotonic,
        ),
        name="backup-restore-stage",
        log_exceptions=False,
    )
    stage_task.add_done_callback(_consume_restore_stage_task_exception)
    stage_succeeded = False
    try:
        sleep_seconds = float(progress_interval_seconds)
        if deadline_monotonic is not None:
            sleep_seconds = min(sleep_seconds, 1.0)
        last_status_update_monotonic: float | None = None
        status_update_interval_seconds = max(2.0, float(progress_interval_seconds))
        while not stage_task.done():
            if registry is not None:
                now_monotonic = time.monotonic()
                if (
                    last_status_update_monotonic is None
                    or (now_monotonic - last_status_update_monotonic)
                    >= status_update_interval_seconds
                ):
                    await update_status_noncritical(
                        registry=registry,
                        task_id=task_id,
                        new_status=TaskStatus.WORKING,
                        log=get_logger(LOGGER_NAME),
                        operation=OPERATION_PROGRESS,
                        message="Failed to update restore copy status.",
                        status_message=f"Restoring {rel_path}",
                        level="debug",
                    )
                    last_status_update_monotonic = now_monotonic
            await asyncio.sleep(sleep_seconds)
        restored_size, restored_hash = await stage_task
        verify_staged_item(
            restored_size=restored_size,
            restored_hash=restored_hash,
            expected_size=entry.size_bytes,
            expected_hash=entry.sha256_hash,
            rel_path=rel_path,
        )
        stage_succeeded = True
    except asyncio.CancelledError:
        stage_task.cancel()
        await cancel_and_await_task(stage_task)
        raise
    finally:
        if not stage_succeeded:
            await cleanup_staging_path(
                staged_paths.staging_path,
                log=get_logger(LOGGER_NAME),
                operation="app.backup.restore_execution.restore_item.cleanup",
            )
    return _PreparedRestore(rel_path, staged_paths, is_directory_target)


async def _cleanup_prepared(
    prepared: list[_PreparedRestore],
    *,
    logger: LoggerProtocol,
) -> None:
    for staged in prepared:
        await cleanup_staging_path(
            staged.staged_paths.staging_path,
            log=logger,
            operation="app.backup.restore_execution.restore_item.cleanup",
        )


async def _report_restored_item(
    *,
    event_bus: EventBusProtocol,
    registry: TaskRegistryProtocol | None,
    task_id: str,
    user_id: int,
    rel_path: str,
    index: int,
    total: int,
) -> None:
    progress_percent = min(99, max(1, int(index / max(1, total) * 99)))
    await report_task_item_progress(
        event_bus=event_bus,
        registry=registry,
        task_id=task_id,
        user_id=user_id,
        percent=progress_percent,
        rel_path=rel_path,
        event_message="Restored item",
        status_message=f"Restored {rel_path}",
        log=get_logger(LOGGER_NAME),
        publish_operation=OPERATION_PUBLISH,
        publish_failure_message="Failed to publish backup restore progress event.",
        publish_details={"task_id": str(task_id), "rel_path": str(rel_path)},
        progress_operation=OPERATION_PROGRESS,
        progress_failure_message="Failed to update restore progress.",
    )


def _consume_restore_stage_task_exception(task: asyncio.Task[tuple[int, str]]) -> None:
    if task.cancelled():
        return
    try:
        task.exception()
    except (asyncio.CancelledError, asyncio.InvalidStateError):
        return
