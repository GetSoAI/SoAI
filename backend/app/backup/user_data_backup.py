"""SoAI - Backup user data directories [backend/app/backup/user_data_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.backup.backup_removal import safe_cleanup_path
from app.backup.copy_no_symlinks.tree_copy import (
    sync_copy_directory_and_hash_no_symlinks,
)
from core.backup.paths import (
    get_backup_relative_files_path,
    get_backup_relative_wallpaper_path,
)
from core.backup.types import BackupManifestFiles
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_makedirs
from core.logging.protocols import StandardLogger
from core.meta.paths import join_data_abs

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("backup_user_data",)

OPERATION = "app.backup.user_data_backup.backup_user_data"


async def backup_user_data(
    *,
    wallpaper_path: str,
    files_path: str,
    dest_dir: str,
    log: StandardLogger,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> tuple[BackupManifestFiles, bool]:
    results: BackupManifestFiles = {}
    had_failure = False
    data_dir = join_data_abs(dest_dir)
    await async_makedirs(data_dir, mode=0o700, exist_ok=True)

    if await async_isdir(wallpaper_path):
        wallpaper_dest = os.path.join(data_dir, "wallpaper")
        try:
            size, directory_hash = await asyncio.to_thread(
                sync_copy_directory_and_hash_no_symlinks,
                wallpaper_path,
                wallpaper_dest,
                write_reservation=disk_reservation,
            )
            results[get_backup_relative_wallpaper_path()] = {
                "type": "directory",
                "sha256": directory_hash,
                "size": int(size),
            }
        except RECOVERABLE_EXCEPTIONS as exception:
            had_failure = True
            log_exception(
                log,
                exception,
                message="Failed to backup wallpaper directory",
                operation=OPERATION,
                level="warning",
            )
            await safe_cleanup_path(
                wallpaper_dest,
                operation="app.backup.user_data_backup.backup_user_data",
                is_directory=True,
                log=log,
            )

    if await async_isdir(files_path):
        files_dest = os.path.join(data_dir, "files")
        try:
            size, directory_hash = await asyncio.to_thread(
                sync_copy_directory_and_hash_no_symlinks,
                files_path,
                files_dest,
                write_reservation=disk_reservation,
            )
            results[get_backup_relative_files_path()] = {
                "type": "directory",
                "sha256": directory_hash,
                "size": int(size),
            }
        except RECOVERABLE_EXCEPTIONS as exception:
            had_failure = True
            log_exception(
                log,
                exception,
                message="Failed to backup files directory",
                operation=OPERATION,
                level="warning",
            )
            await safe_cleanup_path(
                files_dest,
                operation="app.backup.user_data_backup.backup_user_data",
                is_directory=True,
                log=log,
            )

    return results, not had_failure
