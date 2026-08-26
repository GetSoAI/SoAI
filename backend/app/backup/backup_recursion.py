"""SoAI - Backup recursion safety checks [backend/app/backup/backup_recursion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from app.backup.backup_target_paths import (
    get_enabled_backup_targets,
    get_files_storage_path,
    get_wallpaper_path,
)
from app.backup.backup_target_paths_extra import get_logs_path
from app.backup.internal_protocols import ConfigProviderProtocol, FilesProviderProtocol
from core.files.path_policy import is_path_overlap_with_base
from core.filesystem.async_queries import async_path_exists

__all__ = ("is_backup_recursion_safe",)


async def is_backup_recursion_safe(
    backups_path: str,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> bool:
    backups_real = await asyncio.to_thread(os.path.realpath, backups_path)
    targets = get_enabled_backup_targets(config)
    paths_to_check: list[str] = []
    if targets.get("USER_DATA"):
        paths_to_check.append(get_files_storage_path(config, files))
        paths_to_check.append(get_wallpaper_path(config, files))
    if targets.get("LOGS"):
        paths_to_check.append(get_logs_path(config, files))
    for path in paths_to_check:
        if not await async_path_exists(path):
            continue
        path_real = await asyncio.to_thread(os.path.realpath, path)
        if is_path_overlap_with_base(backups_real, path_real):
            return False
    return True
