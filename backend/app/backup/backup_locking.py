"""SoAI - Backup lock and path helpers [backend/app/backup/backup_locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from filelock import BaseFileLock, FileLock, Timeout

from app.backup.backup_removal import (
    remove_tree_no_symlinks,
    sync_remove_tree_no_symlinks,
)
from app.backup.restore_staging_cleanup import cleanup_stale_restore_staging_artifacts
from app.backup.stale_artifact_scanning import sync_collect_stale_paths_by_mtime
from core.backup.manifest import validate_backup_id
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ConflictError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_islink, async_path_exists
from core.logging.protocols import LoggerProtocol
from core.timing.durations import days_to_seconds
from core.timing.epoch import epoch_seconds_float

__all__ = (
    "acquire_operations_lock",
    "acquire_operations_lock_or_conflict",
    "get_operations_lock_path",
    "release_operations_lock",
    "resolve_backup_path",
    "startup_housekeeping_backups_root",
)

OPERATION_APP_BACKUP_BACKUP_LOCKING_RELEASE_IF_LOCKED = (
    "app.backup.backup_locking.release_if_locked"
)


OPERATION_UTILS_BACKUP_STARTUP_HOUSEKEEPING_BACKUPS_ROOT_EXPORTS = (
    "utils_backup.startup_housekeeping_backups_root.exports"
)
OPERATION_UTILS_BACKUP_STARTUP_HOUSEKEEPING_BACKUPS_ROOT_SNAPSHOT = (
    "utils_backup.startup_housekeeping_backups_root.snapshot"
)
OPERATION_UTILS_BACKUP_STARTUP_HOUSEKEEPING_BACKUPS_ROOT_RESTORE_STAGING = (
    "utils_backup.startup_housekeeping_backups_root.restore_staging"
)


def get_operations_lock_path(backups_path: str) -> str:
    if not isinstance(backups_path, str) or not backups_path.strip():
        raise ValidationError("backups_path is required.")
    return os.path.join(backups_path, ".backup_operations.lock")


def resolve_backup_path(backups_path: str, backup_id: str) -> str:
    if not isinstance(backups_path, str) or not backups_path.strip():
        raise ValidationError("backups_path is required.")
    normalized_backup_id = validate_backup_id(backup_id)
    candidate = os.path.join(backups_path, normalized_backup_id)
    backups_root_real = os.path.realpath(backups_path)
    candidate_real = os.path.realpath(candidate)
    if candidate_real != os.path.join(backups_root_real, normalized_backup_id):
        raise SecurityError("Resolved backup path escapes backups root.")
    return candidate_real


_OPERATION_LOCK_POLL_INTERVAL_SECONDS = 0.05


async def _acquire_file_lock(
    lock: BaseFileLock,
    *,
    timeout_seconds: float,
) -> None:
    deadline: MonotonicDeadline | None
    if timeout_seconds < 0:
        deadline = None
    else:
        deadline = deadline_after(timeout_seconds)

    while True:
        try:
            lock.acquire()
            return
        except Timeout:
            if deadline is None or not deadline.expired():
                await asyncio.sleep(_OPERATION_LOCK_POLL_INTERVAL_SECONDS)
                continue
            raise


async def _release_if_locked(
    lock: BaseFileLock,
    *,
    log: LoggerProtocol | None,
    message: str,
    operation: str,
) -> None:
    try:
        if lock.is_locked:
            lock.release()
    except RECOVERABLE_EXCEPTIONS as exception:
        if log is None:
            return
        log_exception(
            log,
            exception,
            message=message,
            operation=OPERATION_APP_BACKUP_BACKUP_LOCKING_RELEASE_IF_LOCKED,
            details={"release_operation": operation},
            level="warning",
        )


async def acquire_operations_lock(
    backups_path: str,
    *,
    timeout_seconds: float,
) -> BaseFileLock:
    if not isinstance(backups_path, str) or not backups_path.strip():
        raise ValidationError("backups_path is required.")
    lock_path = get_operations_lock_path(backups_path)

    lock = FileLock(lock_path, timeout=0, thread_local=False)
    try:
        await _acquire_file_lock(lock, timeout_seconds=timeout_seconds)
    except asyncio.CancelledError:
        await asyncio.shield(
            _release_if_locked(
                lock,
                log=None,
                message="Failed to release operations lock during cancellation",
                operation="utils_backup.acquire_operations_lock",
            ),
        )
        raise
    except Timeout as timeout_exception:
        raise StateError(
            f"Failed to acquire operations lock within {timeout_seconds} seconds.",
            details={"lock_path": lock_path},
        ) from timeout_exception

    return lock


async def acquire_operations_lock_or_conflict(
    backups_path: str,
    *,
    timeout_seconds: float,
) -> BaseFileLock:
    if not isinstance(backups_path, str) or not backups_path.strip():
        raise ValidationError("backups_path is required.")
    lock_path = get_operations_lock_path(backups_path)

    lock = FileLock(lock_path, timeout=0, thread_local=False)
    try:
        await _acquire_file_lock(lock, timeout_seconds=timeout_seconds)
    except asyncio.CancelledError:
        await asyncio.shield(
            _release_if_locked(
                lock,
                log=None,
                message="Failed to release operations lock during cancellation",
                operation="utils_backup.acquire_operations_lock_or_conflict",
            ),
        )
        raise
    except Timeout as timeout_exception:
        raise ConflictError(
            "Another backup operation is in progress. Retry once it completes.",
            details={"lock_path": lock_path, "timeout_seconds": timeout_seconds},
        ) from timeout_exception

    return lock


async def release_operations_lock(lock: BaseFileLock, *, log: LoggerProtocol) -> None:
    await asyncio.shield(
        _release_if_locked(
            lock,
            log=log,
            message="Failed to release operations lock",
            operation="utils_backup.release_operations_lock",
        ),
    )


async def startup_housekeeping_backups_root(
    backups_path: str,
    *,
    log: LoggerProtocol,
) -> None:
    if not isinstance(backups_path, str) or not backups_path.strip():
        return
    lock_path = get_operations_lock_path(backups_path)
    lock = FileLock(lock_path, timeout=0, thread_local=False)
    try:
        try:
            await _acquire_file_lock(lock, timeout_seconds=0)
        except Timeout:
            return

        snapshot_path = os.path.join(backups_path, ".pre_restore_snapshot")
        try:
            if await async_path_exists(snapshot_path):
                await remove_tree_no_symlinks(snapshot_path)
                log.info("Removed stale pre-restore snapshot at %s", snapshot_path)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Failed to remove stale pre-restore snapshot",
                operation=OPERATION_UTILS_BACKUP_STARTUP_HOUSEKEEPING_BACKUPS_ROOT_SNAPSHOT,
                level="warning",
            )

        try:
            await cleanup_stale_restore_staging_artifacts(
                backups_path=backups_path,
                restore_destinations=None,
                log=log,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Failed to clean up stale restore staging artifacts",
                operation=OPERATION_UTILS_BACKUP_STARTUP_HOUSEKEEPING_BACKUPS_ROOT_RESTORE_STAGING,
                level="warning",
            )

        exports_path = os.path.join(backups_path, ".exports")
        max_age_seconds = days_to_seconds(1)
        try:
            if await async_path_exists(exports_path):
                if await async_islink(exports_path):
                    await asyncio.to_thread(sync_remove_tree_no_symlinks, exports_path)
                elif await async_isdir(exports_path):
                    now = epoch_seconds_float()
                    expired_paths = await asyncio.to_thread(
                        sync_collect_stale_paths_by_mtime,
                        exports_path,
                        now_seconds=now,
                        max_age_seconds=float(max_age_seconds),
                    )
                    for expired_path in expired_paths:
                        await asyncio.to_thread(sync_remove_tree_no_symlinks, expired_path)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Failed to clean up export archives",
                operation=OPERATION_UTILS_BACKUP_STARTUP_HOUSEKEEPING_BACKUPS_ROOT_EXPORTS,
                level="warning",
            )
    finally:
        await asyncio.shield(
            _release_if_locked(
                lock,
                log=log,
                message="Failed to release operations lock during startup housekeeping",
                operation="utils_backup.startup_housekeeping_backups_root.release",
            ),
        )
