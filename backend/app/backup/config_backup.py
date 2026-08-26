"""SoAI - Backup config.yaml with locking [backend/app/backup/config_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from filelock import Timeout

from app.backup.copy_no_symlinks.file_copy import sync_copy_file_and_hash_no_symlinks
from core.backup.types import BackupFileEntry
from core.errors.exception_logging import log_exception
from core.files.locking import guarded_file_lock
from core.filesystem.async_queries import async_makedirs, async_path_exists
from core.logging.trace import get_logger
from core.meta.paths import join_data_abs

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("backup_config_file",)

LOGGER_NAME = "SoAI.app.backup.config_backup"
OPERATION = "app.backup.config_backup.backup_config_file"


async def backup_config_file(
    *,
    config_path: str,
    dest_dir: str,
    lock_path: str,
    lock_timeout_seconds: float,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> BackupFileEntry | None:
    logger = get_logger(LOGGER_NAME)
    if not await async_path_exists(config_path):
        logger.warning("config.yaml not found.")
        return None
    dest_path = join_data_abs(dest_dir, "config", "config.yaml")
    await async_makedirs(os.path.dirname(dest_path), mode=0o700, exist_ok=True)

    def on_timeout(_: Timeout) -> Exception:
        return RuntimeError(
            f"Could not acquire lock on config.yaml for backup ({lock_timeout_seconds}s).",
        )

    try:
        with guarded_file_lock(lock_path, timeout=lock_timeout_seconds, on_timeout=on_timeout):
            size, file_hash = await asyncio.to_thread(
                sync_copy_file_and_hash_no_symlinks,
                config_path,
                dest_path,
                write_reservation=disk_reservation,
            )
    except RuntimeError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to backup config.yaml",
            operation=OPERATION,
            level="warning",
        )
        return None
    return {"type": "file", "sha256": file_hash, "size": int(size)}
