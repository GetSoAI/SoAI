"""SoAI - Restore staging copy and atomic commit helpers [backend/app/backup/restore_staging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from functools import partial

from app.backup.backup_removal import (
    remove_tree_no_symlinks,
    sync_remove_tree_no_symlinks,
)
from app.backup.copy_no_symlinks.file_copy import sync_copy_file_and_hash_no_symlinks
from app.backup.copy_no_symlinks.tree_copy import (
    sync_copy_directory_and_hash_no_symlinks,
    sync_fsync_directory_tree,
)
from app.backup.restore_destinations import ensure_restore_destination_is_safe
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.temp_files import (
    create_secure_temp_directory,
    create_secure_temp_file_descriptor,
)
from core.filesystem.atomic_write_primitives import fsync_directory
from core.logging.protocols import LoggerProtocol

__all__ = (
    "StagedRestorePaths",
    "allocate_staging_paths",
    "cleanup_staging_path",
    "commit_staged_item",
    "stage_restore_item",
    "verify_staged_item",
)

_STAGING_PREFIX = ".soai_restore_staging."


@dataclass(frozen=True, slots=True)
class StagedRestorePaths:
    destination_path: str
    staging_path: str


def _allocate_staging_file_path(destination_path: str) -> str:
    if not isinstance(destination_path, str) or not destination_path.strip():
        raise ValidationError("destination_path is required.")
    destination_directory = os.path.dirname(destination_path)
    if not destination_directory:
        raise ValidationError("destination_path must have a parent directory.")
    fd, staging_path = create_secure_temp_file_descriptor(
        directory=destination_directory,
        prefix=_STAGING_PREFIX,
        suffix=".file",
    )
    os.close(fd)
    try:
        os.remove(staging_path)
    except FileNotFoundError:
        return staging_path
    return staging_path


def _allocate_staging_directory_path(destination_path: str) -> str:
    if not isinstance(destination_path, str) or not destination_path.strip():
        raise ValidationError("destination_path is required.")
    destination_directory = os.path.dirname(destination_path)
    if not destination_directory:
        raise ValidationError("destination_path must have a parent directory.")
    return create_secure_temp_directory(
        prefix=_STAGING_PREFIX,
        suffix=".dir",
        directory=destination_directory,
    )


def allocate_staging_paths(destination_path: str, *, is_directory: bool) -> StagedRestorePaths:
    ensure_restore_destination_is_safe(destination_path)
    staging_path = (
        _allocate_staging_directory_path(destination_path)
        if is_directory
        else _allocate_staging_file_path(destination_path)
    )
    return StagedRestorePaths(destination_path=destination_path, staging_path=staging_path)


def _sync_commit_staged_item(
    staged_paths: StagedRestorePaths,
    *,
    is_directory: bool,
) -> None:
    destination_path = staged_paths.destination_path
    staging_path = staged_paths.staging_path
    ensure_restore_destination_is_safe(destination_path)
    destination_directory = os.path.dirname(destination_path)
    if destination_directory:
        os.makedirs(destination_directory, mode=0o700, exist_ok=True)
    if os.path.lexists(destination_path):
        if is_directory or os.path.isdir(destination_path):
            sync_remove_tree_no_symlinks(destination_path)
    try:
        os.replace(staging_path, destination_path)
    except OSError as exception:
        if exception.errno == errno.EXDEV:
            raise StateError(
                (
                    "Restore commit failed due to cross-device destination; "
                    "atomic restore is unsupported for this path."
                ),
                details={"destination_path": destination_path},
                operation="app.backup.restore_staging.commit",
            ) from exception
        raise
    fsync_directory(destination_directory, strict=True)


async def commit_staged_item(
    staged_paths: StagedRestorePaths,
    *,
    is_directory: bool,
) -> None:
    await run_joined_thread_call(
        partial(_sync_commit_staged_item, staged_paths, is_directory=is_directory),
        task_name="backup-restore-stage-commit",
    )


async def cleanup_staging_path(
    staging_path: str,
    *,
    log: LoggerProtocol,
    operation: str,
) -> None:
    if not isinstance(staging_path, str) or not staging_path.strip():
        return
    try:
        await remove_tree_no_symlinks(staging_path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message="Failed to clean up restore staging path.",
            operation=operation,
            details={"staging_path": staging_path},
            level="warning",
        )


async def stage_restore_item(
    *,
    source_path: str,
    staged_paths: StagedRestorePaths,
    is_directory: bool,
    deadline_monotonic: float | None,
) -> tuple[int, str]:
    if is_directory:
        copy_result = await run_joined_thread_call(
            partial(
                sync_copy_directory_and_hash_no_symlinks,
                source_path,
                staged_paths.staging_path,
                deadline_monotonic=deadline_monotonic,
                allow_existing_empty_destination=True,
            ),
            task_name="backup-restore-stage-directory-copy",
        )
        await run_joined_thread_call(
            sync_fsync_directory_tree,
            staged_paths.staging_path,
            task_name="backup-restore-stage-directory-sync",
        )
        return copy_result
    return await run_joined_thread_call(
        partial(
            sync_copy_file_and_hash_no_symlinks,
            source_path,
            staged_paths.staging_path,
            deadline_monotonic=deadline_monotonic,
        ),
        task_name="backup-restore-stage-file-copy",
    )


def verify_staged_item(
    *,
    restored_size: int,
    restored_hash: str,
    expected_size: int,
    expected_hash: str,
    rel_path: str,
) -> None:
    if restored_size != expected_size:
        raise SecurityError(f"Restore size mismatch for {rel_path}.")
    if restored_hash != expected_hash:
        raise SecurityError(f"Restore hash mismatch for {rel_path}.")
