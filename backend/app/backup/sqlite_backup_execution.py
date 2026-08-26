"""SoAI - SQLite backup target execution [backend/app/backup/sqlite_backup_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING

from app.backup.manifest_entries import build_file_manifest_entry
from app.backup.sqlite_backup import (
    remove_sqlite_backup_destination_files,
    sync_sqlite_backup,
)
from app.backup.sqlite_backup_source import get_sqlite_snapshot_content_bytes
from app.backup.task_registry_reporting import update_status_noncritical
from app.backup.task_result_validation import require_backup_bool_value
from core.backup.types import BackupFileEntry
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_makedirs, async_path_exists
from core.meta.paths import join_data_abs
from core.tasks.enums import TaskStatus
from core.timing.constants import BACKGROUND_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        DiskSpaceWriteClaimProtocol,
    )
    from core.logging.protocols import StandardLogger
    from core.tasks.protocols import TaskRegistryLifecycleView

__all__ = ("backup_sqlite_database",)

OPERATION = "app.backup.sqlite_backup.backup_sqlite_database"
OPERATION_ACTIVITY = "app.backup.sqlite_backup.backup_sqlite_database.activity"


async def _refresh_sqlite_backup_activity(
    *,
    registry: TaskRegistryLifecycleView,
    task_id: str,
    log: StandardLogger,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=BACKGROUND_TIMEOUT_SEC)
        except TimeoutError:
            await update_status_noncritical(
                registry=registry,
                task_id=task_id,
                new_status=TaskStatus.WORKING,
                log=log,
                operation=OPERATION_ACTIVITY,
                message="Failed to refresh SQLite backup task activity.",
                status_message="Backing up database",
                level="debug",
            )


async def _run_sqlite_backup_with_activity(
    *,
    db_path: str,
    dest_path: str,
    sqlite_backup_timeout_seconds: float,
    sqlite_backup_timeout_seconds_per_gib: float,
    log: StandardLogger,
    task_registry: TaskRegistryLifecycleView | None,
    task_id: str | None,
) -> bool:
    if task_registry is None or not task_id:
        return await asyncio.to_thread(
            sync_sqlite_backup,
            db_path,
            dest_path,
            timeout_seconds=sqlite_backup_timeout_seconds,
            timeout_seconds_per_gib=sqlite_backup_timeout_seconds_per_gib,
        )
    stop_event = asyncio.Event()
    activity_task = create_ephemeral_task(
        _refresh_sqlite_backup_activity(
            registry=task_registry,
            task_id=task_id,
            log=log,
            stop_event=stop_event,
        ),
        name=f"sqlite-backup-activity-{task_id}",
    )
    try:
        return await asyncio.to_thread(
            sync_sqlite_backup,
            db_path,
            dest_path,
            timeout_seconds=sqlite_backup_timeout_seconds,
            timeout_seconds_per_gib=sqlite_backup_timeout_seconds_per_gib,
        )
    finally:
        stop_event.set()
        await cancel_and_await(
            (activity_task,),
            logger=log,
            task_label="sqlite backup activity task",
            log_level=10,
        )


async def backup_sqlite_database(
    *,
    db_path: str,
    dest_dir: str,
    sqlite_backup_timeout_seconds: float,
    sqlite_backup_timeout_seconds_per_gib: float,
    log: StandardLogger,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
    task_registry: TaskRegistryLifecycleView | None,
    task_id: str | None,
) -> BackupFileEntry | None:
    if not await async_path_exists(db_path):
        log.debug("Database file not found: %s", db_path)
        return None
    database_dir = join_data_abs(dest_dir, "database")
    await async_makedirs(database_dir, mode=0o700, exist_ok=True)
    dest_path = os.path.join(database_dir, "soai.db")
    reserved_bytes = await asyncio.to_thread(get_sqlite_snapshot_content_bytes, db_path)
    write_claim = _open_destination_write_claim(disk_reservation, reserved_bytes)
    claim_scope: AbstractContextManager[DiskSpaceWriteClaimProtocol | None] = (
        nullcontext() if write_claim is None else write_claim
    )
    with claim_scope:
        try:
            integrity_ok = await _run_sqlite_backup_with_activity(
                db_path=db_path,
                dest_path=dest_path,
                sqlite_backup_timeout_seconds=sqlite_backup_timeout_seconds,
                sqlite_backup_timeout_seconds_per_gib=sqlite_backup_timeout_seconds_per_gib,
                log=log,
                task_registry=task_registry,
                task_id=task_id,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="SQLite backup failed",
                operation=OPERATION,
            )
            destination_discarded = await _cleanup_partial_sqlite_backup(dest_path, log)
            _resolve_write_claim_after_failure(
                write_claim,
                destination_discarded=destination_discarded,
            )
            return None
        if write_claim is not None:
            write_claim.commit()
    if not await async_path_exists(dest_path):
        return None
    entry = await build_file_manifest_entry(dest_path)
    entry["integrity_ok"] = require_backup_bool_value(
        integrity_ok,
        error_message="SQLite backup integrity result must be a bool.",
    )
    return entry


def _open_destination_write_claim(
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
    reserved_bytes: int,
) -> DiskSpaceWriteClaimProtocol | None:
    if reserved_bytes <= 0:
        return None
    if disk_reservation is None:
        raise StateError("Disk reservation is required for positive writes.")
    return disk_reservation.claim_write_bytes(reserved_bytes)


def _resolve_write_claim_after_failure(
    write_claim: DiskSpaceWriteClaimProtocol | None,
    *,
    destination_discarded: bool,
) -> None:
    if write_claim is None:
        return
    if destination_discarded:
        write_claim.rollback()
        return
    write_claim.commit()


async def _cleanup_partial_sqlite_backup(dest_path: str, log: StandardLogger) -> bool:
    try:
        removed_paths = await asyncio.to_thread(remove_sqlite_backup_destination_files, dest_path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message="Failed to clean up partial SQLite backup files.",
            operation=OPERATION,
        )
        return False
    if removed_paths:
        log.debug("Cleaned up partial database backup files at %s", dest_path)
    return True
