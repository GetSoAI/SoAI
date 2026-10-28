"""SoAI - Backup user data directories [backend/app/backup/user_data_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import posixpath
from functools import partial
from typing import TYPE_CHECKING

from app.backup.backup_removal import safe_cleanup_path
from app.backup.copy_no_symlinks.tree_copy import (
    sync_copy_directory_and_hash_no_symlinks,
)
from core.backup.types import BackupManifestFiles
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_makedirs
from core.logging.protocols import StandardLogger

if TYPE_CHECKING:
    from app.backup.internal_protocols import UserDataSource
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("backup_user_data",)

OPERATION = "app.backup.user_data_backup.backup_user_data"


async def backup_user_data(
    *,
    sources: tuple[UserDataSource, ...],
    dest_dir: str,
    log: StandardLogger,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> tuple[BackupManifestFiles, bool]:
    results: BackupManifestFiles = {}
    had_failure = False
    for source in sources:
        if not await async_isdir(source.source_path):
            continue
        destination = os.path.join(dest_dir, *source.archive_path.split(posixpath.sep))
        await async_makedirs(os.path.dirname(destination), mode=0o700, exist_ok=True)
        try:
            size, directory_hash = await run_joined_thread_call(
                partial(
                    sync_copy_directory_and_hash_no_symlinks,
                    source.source_path,
                    destination,
                    write_reservation=disk_reservation,
                ),
                task_name="backup-user-data-directory-copy",
                retain_resources_until_complete=True,
            )
            results[source.archive_path] = {
                "type": "directory",
                "sha256": directory_hash,
                "size": int(size),
            }
        except RECOVERABLE_EXCEPTIONS as exception:
            had_failure = True
            log_exception(
                log,
                exception,
                message="Failed to backup user data directory",
                operation=OPERATION,
                details={"archive_path": source.archive_path},
                level="warning",
            )
            await safe_cleanup_path(
                destination,
                operation=OPERATION,
                is_directory=True,
                log=log,
            )
    return results, not had_failure
