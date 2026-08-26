"""SoAI - Backup root setup helpers [backend/app/backup/backup_root_setup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.backup.backup_locking import startup_housekeeping_backups_root
from app.backup.copy_no_symlinks.permissions import ensure_backup_directory_permissions
from core.files.operations import ensure_dirs_exist
from core.logging.protocols import LoggerProtocol

__all__ = ("prepare_backup_root",)


async def prepare_backup_root(
    backups_path: str,
    *,
    is_windows: bool,
    log: LoggerProtocol,
) -> None:
    await ensure_dirs_exist([backups_path])
    await ensure_backup_directory_permissions(
        backups_path,
        is_windows=is_windows,
        force_walk=True,
    )
    await startup_housekeeping_backups_root(backups_path, log=log)
