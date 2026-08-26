"""SoAI - Backup installed plugin configuration files [backend/app/backup/plugin_config_backup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from filelock import Timeout

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.copy_no_symlinks.file_copy import sync_copy_file_and_hash_no_symlinks
from core.backup.paths import get_backup_relative_plugin_config_path
from core.backup.types import BackupManifestFiles
from core.config.protocols import ConfigManagerProtocol
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.locking import guarded_file_lock
from core.filesystem.async_queries import (
    async_isdir,
    async_isfile,
    async_makedirs,
    async_path_exists,
)
from core.logging.trace import get_logger
from core.plugins.file_suffixes import PLUGIN_CONFIG_FILE_SUFFIX

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = ("backup_plugin_configs",)

LOGGER_NAME = "SoAI.app.backup.plugin_config_backup"
OPERATION = "app.backup.plugin_config_backup.backup_plugin_configs"


async def backup_plugin_configs(
    *,
    plugins_path: str,
    dest_dir: str,
    config_manager: ConfigManagerProtocol,
    lock_timeout_seconds: float,
    disk_reservation: DiskSpaceReservationLeaseProtocol | None,
) -> tuple[BackupManifestFiles, bool]:
    logger = get_logger(LOGGER_NAME)
    results: BackupManifestFiles = {}
    had_failure = False
    if not await async_isdir(plugins_path):
        return results, True
    plugins_dest = os.path.join(dest_dir, "plugins")
    await async_makedirs(plugins_dest, mode=0o700, exist_ok=True)
    entries = await asyncio.to_thread(os.listdir, plugins_path)
    for entry in sorted(entries):
        if not entry.endswith(PLUGIN_CONFIG_FILE_SUFFIX):
            continue
        src_path = os.path.join(plugins_path, entry)
        if not await async_isfile(src_path):
            continue
        dest_path = os.path.join(plugins_dest, entry)
        lock_path = config_manager.get_lock_path(src_path)

        def on_timeout(
            _: Timeout,
            plugin_entry: str = entry,
            timeout: float = lock_timeout_seconds,
        ) -> Exception:
            return RuntimeError(
                f"Could not acquire lock on {plugin_entry} for backup ({timeout}s).",
            )

        try:
            with guarded_file_lock(lock_path, timeout=lock_timeout_seconds, on_timeout=on_timeout):
                size, file_hash = await asyncio.to_thread(
                    sync_copy_file_and_hash_no_symlinks,
                    src_path,
                    dest_path,
                    write_reservation=disk_reservation,
                )
            results[get_backup_relative_plugin_config_path(entry)] = {
                "type": "file",
                "sha256": file_hash,
                "size": int(size),
            }
        except RECOVERABLE_EXCEPTIONS as exception:
            had_failure = True
            log_exception(
                logger,
                exception,
                message=f"Failed to backup plugin config: {entry}",
                operation=OPERATION,
                level="warning",
            )
            if await async_path_exists(dest_path):
                try:
                    await asyncio.to_thread(sync_remove_tree_no_symlinks, dest_path)
                except RECOVERABLE_EXCEPTIONS as cleanup_exception:
                    log_exception(
                        logger,
                        cleanup_exception,
                        message=f"Failed to clean up partial plugin config: {entry}",
                        operation=OPERATION,
                        level="warning",
                    )
    return results, not had_failure
