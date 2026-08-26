"""SoAI - Backup SoAI log directory [backend/app/backup/logs_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.backup.backup_removal import safe_cleanup_path
from app.backup.copy_no_symlinks.tree_copy import (
    sync_copy_directory_and_hash_no_symlinks,
)
from core.backup.paths import get_backup_relative_logs_path
from core.backup.types import BackupManifestFiles
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_makedirs
from core.logging.protocols import StandardLogger
from core.meta.paths import join_data_abs

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("backup_logs",)

OPERATION = "app.backup.logs_backup.backup_logs"


async def backup_logs(
    *,
    logs_path: str,
    dest_dir: str,
    log: StandardLogger,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> tuple[BackupManifestFiles, bool]:
    results: BackupManifestFiles = {}
    if not await async_isdir(logs_path):
        return results, True
    data_dir = join_data_abs(dest_dir)
    await async_makedirs(data_dir, mode=0o700, exist_ok=True)
    logs_dest = os.path.join(data_dir, "logs")
    try:
        size, directory_hash = await asyncio.to_thread(
            sync_copy_directory_and_hash_no_symlinks,
            logs_path,
            logs_dest,
            write_reservation=disk_reservation,
        )
        results[get_backup_relative_logs_path()] = {
            "type": "directory",
            "sha256": directory_hash,
            "size": int(size),
        }
        return results, True
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message="Failed to backup logs directory",
            operation=OPERATION,
            level="warning",
        )
        await safe_cleanup_path(
            logs_dest,
            operation="app.backup.logs_backup.backup_logs",
            is_directory=True,
            log=log,
        )
        return results, False
