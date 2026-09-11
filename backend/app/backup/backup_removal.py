"""SoAI - Backup removal helpers [backend/app/backup/backup_removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SecurityError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_path_exists
from core.filesystem.path_coercion import normalize_filesystem_path
from core.logging.protocols import LoggerProtocol

__all__ = (
    "remove_tree_no_symlinks",
    "safe_cleanup_path",
    "sync_remove_tree_no_symlinks",
)

OPERATION_APP_BACKUP_BACKUP_REMOVAL_SAFE_CLEANUP_PATH = (
    "app.backup.backup_removal.safe_cleanup_path"
)


def sync_remove_tree_no_symlinks(path: str) -> None:
    if not path.strip():
        raise ValidationError("path is required.")
    path = normalize_filesystem_path(path)
    try:
        stat_info = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exception:
        raise SecurityError(f"Failed to stat path for removal: {path}") from exception
    if stat.S_ISLNK(stat_info.st_mode):
        os.unlink(path)
        return
    if stat.S_ISREG(stat_info.st_mode):
        os.remove(path)
        return
    if not stat.S_ISDIR(stat_info.st_mode):
        os.remove(path)
        return
    with os.scandir(path) as it:
        for entry in it:
            entry_path = entry.path
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(entry_stat.st_mode):
                os.unlink(entry_path)
            elif stat.S_ISDIR(entry_stat.st_mode):
                sync_remove_tree_no_symlinks(entry_path)
            else:
                os.remove(entry_path)
    os.rmdir(path)


async def remove_tree_no_symlinks(path: str) -> None:
    await run_joined_thread_call(
        sync_remove_tree_no_symlinks,
        path,
        task_name="backup-remove-tree",
    )


async def safe_cleanup_path(
    path: str,
    *,
    operation: str,
    is_directory: bool,
    log: LoggerProtocol,
) -> None:
    if not path.strip():
        return
    if not await async_path_exists(path):
        return
    try:
        await remove_tree_no_symlinks(path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message=f"Failed to clean up partial backup at {path}",
            operation=OPERATION_APP_BACKUP_BACKUP_REMOVAL_SAFE_CLEANUP_PATH,
            details={
                "cleanup_operation": operation,
                "path": path,
                "is_directory": bool(is_directory),
            },
            level="warning",
        )
