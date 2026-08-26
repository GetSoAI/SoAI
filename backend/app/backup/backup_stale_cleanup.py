"""SoAI - Backup stale partial cleanup [backend/app/backup/backup_stale_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_seconds_float

__all__ = ("cleanup_stale_partial_backups",)

LOGGER_NAME = "SoAI.app.backup.backup_stale_cleanup"
OPERATION = "application_backup.cleanup_stale_parts"


def cleanup_stale_partial_backups(*, backups_path: str, stale_threshold_seconds: float) -> int:
    logger = get_logger(LOGGER_NAME)
    count = 0
    current_time = epoch_seconds_float()
    for entry in os.listdir(backups_path):
        if not entry.endswith(".part"):
            continue
        part_path = os.path.join(backups_path, entry)
        try:
            stat_info = os.lstat(part_path)
            if stat.S_ISLNK(stat_info.st_mode):
                logger.warning("Skipping symlink during stale cleanup: %s", entry)
                continue
            age_seconds = current_time - stat_info.st_mtime
            if age_seconds < stale_threshold_seconds:
                continue
            if stat.S_ISDIR(stat_info.st_mode):
                sync_remove_tree_no_symlinks(part_path)
            elif stat.S_ISREG(stat_info.st_mode):
                os.remove(part_path)
            else:
                continue
            count += 1
            logger.info("Cleaned up stale partial backup: %s", entry)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message=f"Failed to clean up stale partial backup: {entry}",
                operation=OPERATION,
                level="warning",
            )
    return count
