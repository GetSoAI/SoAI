"""SoAI - Backup deletion helpers [backend/app/backup/backup_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.backup.backup_locking import (
    acquire_operations_lock,
    release_operations_lock,
    resolve_backup_path,
)
from app.backup.backup_removal import remove_tree_no_symlinks
from app.backup.backup_timeout_settings import get_operations_lock_timeout_seconds
from app.backup.internal_protocols import ConfigProviderProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, SecurityError, StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_islink
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("delete_backup_path",)

OPERATION = "application_backup.delete_backup"


async def delete_backup_path(
    *,
    backups_path: str,
    backup_id: str,
    config: ConfigProviderProtocol,
    backup_lock: asyncio.Lock,
    log: LoggerProtocol,
) -> JSONDict:
    operations_lock = await acquire_operations_lock(
        backups_path,
        timeout_seconds=get_operations_lock_timeout_seconds(config),
    )
    try:
        async with backup_lock:
            backup_path = resolve_backup_path(backups_path, backup_id)
            if not await async_isdir(backup_path):
                raise NotFoundError(
                    f"Backup '{backup_id}' not found.",
                    details={"backup_id": backup_id},
                )
            if await async_islink(backup_path):
                raise SecurityError(
                    "Refusing to delete symlinked backup path.",
                    details={"backup_id": backup_id},
                )
            try:
                await remove_tree_no_symlinks(backup_path)
                log.info("Deleted backup: %s", backup_id)
                return {
                    "backup_id": backup_id,
                    "deleted": True,
                }
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    log,
                    exception,
                    message=f"Failed to delete backup: {backup_id}",
                    operation=OPERATION,
                )
                raise StateError(
                    f"Failed to delete backup '{backup_id}'.",
                    details={"backup_id": backup_id},
                ) from exception
    finally:
        await release_operations_lock(operations_lock, log=log)
