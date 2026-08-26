"""SoAI - Backup marker helpers [backend/app/backup/backup_marker_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os

from app.backup.archive_io import write_marker_file
from app.backup.copy_no_symlinks.permissions import ensure_backup_directory_permissions
from core.files.operations import async_remove_if_exists
from core.logging.protocols import LoggerProtocol

__all__ = (
    "clear_initial_backup_marker",
    "update_initial_backup_marker",
)

OPERATION = "application_backup.initialize.clear_marker"


async def clear_initial_backup_marker(backups_path: str, *, log: LoggerProtocol) -> None:
    if not backups_path.strip():
        return
    marker_path = os.path.join(backups_path, ".first_backup_complete")
    if await async_remove_if_exists(marker_path, logger=log, log_level=logging.DEBUG):
        log.debug("Backup disabled, cleared initial backup marker")


async def update_initial_backup_marker(
    *,
    backups_path: str,
    marker_path: str,
    previous_completed: dict[str, bool],
    targets_completed: dict[str, bool],
    is_windows: bool,
    log: LoggerProtocol,
) -> None:
    merged_completed: dict[str, bool] = dict(previous_completed)
    for target_key, completed in targets_completed.items():
        if completed:
            merged_completed[target_key] = True
    await asyncio.to_thread(
        write_marker_file,
        marker_path,
        targets_completed=merged_completed,
    )
    await ensure_backup_directory_permissions(
        backups_path,
        is_windows=is_windows,
        force_walk=True,
    )
    log.debug("Updated initial backup marker at %s", marker_path)
