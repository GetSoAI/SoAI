"""SoAI - Single-file backup operations for the data directory [backend/app/backup/data_file_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.backup.copy_no_symlinks.file_copy import sync_copy_file_and_hash_no_symlinks
from core.backup.types import BackupFileEntry
from core.filesystem.async_queries import async_makedirs, async_path_exists
from core.logging.trace import get_logger
from core.meta.paths import join_data_abs

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("backup_single_file_to_data_dir",)

LOGGER_NAME = "SoAI.app.backup.data_file_backup"


async def backup_single_file_to_data_dir(
    *,
    source_path: str,
    dest_dir: str,
    dest_filename: str,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
    log_missing: bool = False,
    missing_log_message: str | None = None,
) -> BackupFileEntry | None:
    logger = get_logger(LOGGER_NAME)
    if not await async_path_exists(source_path):
        if log_missing and missing_log_message:
            logger.warning(missing_log_message, source_path)
        return None
    data_dir = join_data_abs(dest_dir)
    await async_makedirs(data_dir, mode=0o700, exist_ok=True)
    dest_path = os.path.join(data_dir, dest_filename)
    size, file_hash = await asyncio.to_thread(
        sync_copy_file_and_hash_no_symlinks,
        source_path,
        dest_path,
        write_reservation=disk_reservation,
    )
    return {"type": "file", "sha256": file_hash, "size": int(size)}
