"""SoAI - Backup create, list, delete, and export operations [backend/app/backup/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.backup.backup_creation import create_backup_internal
from app.backup.backup_deletion import delete_backup_path
from app.backup.backup_export import create_export_archive
from app.backup.backup_listing import build_backup_listing
from app.backup.backup_locking import (
    acquire_operations_lock,
    acquire_operations_lock_or_conflict,
    release_operations_lock,
    resolve_backup_path,
)
from app.backup.backup_timeout_settings import (
    get_export_lock_timeout_seconds,
    get_operations_lock_timeout_seconds,
)
from core.backup.manifest import validate_backup_id
from core.backup.types import BackupCreateResult
from core.errors.exceptions import StateError
from core.logging.rate_limited_logger import RateLimitedLogger
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from app.backup.internal_protocols import (
        BackupServiceContext,
        ConfigProviderProtocol,
    )
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict

__all__ = (
    "execute_create_backup",
    "execute_delete_backup",
    "execute_export_archive",
    "execute_list_backups",
)

LOGGER_NAME = "SoAI.app.backup.operations"


async def execute_create_backup(
    context: BackupServiceContext,
    backups_path: str,
    backup_lock: asyncio.Lock,
    config: ConfigProviderProtocol,
    task_id: str | None = None,
) -> BackupCreateResult:
    logger = get_logger(LOGGER_NAME)
    if not backups_path:
        raise StateError("Backups path is not configured.")
    operations_lock = await acquire_operations_lock(
        backups_path,
        timeout_seconds=get_operations_lock_timeout_seconds(config),
    )
    try:
        async with backup_lock:
            return await create_backup_internal(context, task_id=task_id)
    finally:
        await release_operations_lock(operations_lock, log=logger)


async def execute_list_backups(
    backups_path: str,
    invalid_manifest_log_limiter: RateLimitedLogger,
) -> list[JSONDict]:
    if not backups_path:
        raise StateError("Backups path is not configured.")
    return await build_backup_listing(backups_path, invalid_manifest_log_limiter)


async def execute_delete_backup(
    backups_path: str,
    backup_lock: asyncio.Lock,
    config: ConfigProviderProtocol,
    backup_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    if not backups_path:
        raise StateError("Backups path is not configured.")
    normalized_backup_id = validate_backup_id(backup_id)
    return await delete_backup_path(
        backups_path=backups_path,
        backup_id=normalized_backup_id,
        config=config,
        backup_lock=backup_lock,
        log=logger,
    )


async def execute_export_archive(
    backups_path: str,
    backup_lock: asyncio.Lock,
    config: ConfigProviderProtocol,
    storage_manager: StorageManagerProtocol,
    backup_id: str,
) -> str:
    logger = get_logger(LOGGER_NAME)
    if not backups_path:
        raise StateError("Backup path not configured.")
    normalized_backup_id = validate_backup_id(backup_id)
    backup_path = resolve_backup_path(backups_path, normalized_backup_id)
    operations_lock = await acquire_operations_lock_or_conflict(
        backups_path,
        timeout_seconds=get_export_lock_timeout_seconds(config),
    )
    try:
        return await create_export_archive(
            backups_path=backups_path,
            backup_path=backup_path,
            backup_id=normalized_backup_id,
            backup_lock=backup_lock,
            storage_manager=storage_manager,
        )
    finally:
        await release_operations_lock(operations_lock, log=logger)
