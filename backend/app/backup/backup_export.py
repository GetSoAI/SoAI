"""SoAI - Backup export helpers [backend/app/backup/backup_export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os

from core.archives.reservations import open_write_claim
from core.errors.exceptions import NotFoundError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove_if_exists
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.async_queries import (
    async_isdir,
    async_islink,
    async_makedirs,
    async_path_exists,
)
from core.hardware.protocols_storage import (
    DiskSpaceReservationLeaseProtocol,
    StorageManagerProtocol,
)
from core.logging.trace import get_logger
from files.archive import (
    sync_calculate_backup_export_archive_max_size,
    sync_write_backup_export_archive,
)

__all__ = (
    "allocate_export_archive_path",
    "create_export_archive",
    "ensure_export_directory",
    "reserve_export_disk_space",
    "resolve_export_size",
    "validate_export_source",
    "write_export_archive",
)

LOGGER_NAME = "SoAI.app.backup.backup_export"
EXPORT_ARCHIVE_CONTROL_BYTES = 64 * 1024


def _sync_allocate_export_archive_path(exports_dir: str, backup_id: str) -> str:
    fd, archive_path = create_secure_temp_file_descriptor(
        directory=exports_dir,
        prefix=f"{backup_id}_",
        suffix=".tar.gz",
    )
    os.close(fd)
    return archive_path


async def ensure_export_directory(backups_path: str) -> str:
    exports_dir = os.path.join(backups_path, ".exports")
    if await async_path_exists(exports_dir):
        if not await async_isdir(exports_dir):
            raise ValidationError(
                f"Export directory path exists but is not a directory: {exports_dir}",
            )
        if await async_islink(exports_dir):
            raise SecurityError(
                "Refusing to use symlinked export directory.",
                details={"path": exports_dir},
            )
        return exports_dir
    await async_makedirs(exports_dir, mode=0o700, exist_ok=True)
    return exports_dir


async def validate_export_source(backup_path: str, backup_id: str) -> None:
    if not await async_isdir(backup_path):
        raise NotFoundError(
            f"Backup '{backup_id}' not found.",
            details={"backup_id": backup_id},
        )
    if await async_islink(backup_path):
        raise SecurityError(
            "Refusing to export symlinked backup path.",
            details={"backup_id": backup_id},
        )


async def allocate_export_archive_path(exports_dir: str, backup_id: str) -> str:
    return await asyncio.to_thread(_sync_allocate_export_archive_path, exports_dir, backup_id)


async def resolve_export_size(backup_path: str, backup_id: str) -> int:
    backup_size_value = await asyncio.to_thread(
        sync_calculate_backup_export_archive_max_size,
        backup_path,
        backup_id,
    )
    if (
        not isinstance(backup_size_value, int)
        or isinstance(backup_size_value, bool)
        or backup_size_value < 0
    ):
        raise StateError(
            "Failed to calculate backup size for export.",
            details={
                "backup_id": backup_id,
                "backup_path": backup_path,
            },
        )
    return backup_size_value


def reserve_export_disk_space(
    storage_manager: StorageManagerProtocol,
    backups_path: str,
    backup_id: str,
    backup_path: str,
    required_bytes: int,
) -> DiskSpaceReservationLeaseProtocol:
    return storage_manager.reserve_disk_space(
        path=backups_path,
        required_bytes=required_bytes,
        operation="application_backup.create_backup_export_archive",
        details={
            "purpose": "backup_export_archive",
            "backup_id": backup_id,
            "backup_path": backup_path,
            "required_bytes": required_bytes,
        },
    )


async def write_export_archive(backup_path: str, archive_path: str, backup_id: str) -> None:
    await asyncio.to_thread(
        sync_write_backup_export_archive,
        backup_path,
        archive_path,
        backup_id,
    )


async def create_export_archive(
    *,
    backups_path: str,
    backup_path: str,
    backup_id: str,
    backup_lock: asyncio.Lock,
    storage_manager: StorageManagerProtocol,
) -> str:
    logger = get_logger(LOGGER_NAME)
    await validate_export_source(backup_path, backup_id)
    archive_path = ""
    reservation: DiskSpaceReservationLeaseProtocol | None = None
    try:
        async with backup_lock:
            archive_bytes = await resolve_export_size(backup_path, backup_id)
            required_bytes = archive_bytes + EXPORT_ARCHIVE_CONTROL_BYTES
            reservation = reserve_export_disk_space(
                storage_manager,
                backups_path,
                backup_id,
                backup_path,
                required_bytes,
            )
            with open_write_claim(reservation, size_bytes=required_bytes) as claim:
                exports_dir = await ensure_export_directory(backups_path)
                archive_path = await allocate_export_archive_path(
                    exports_dir,
                    backup_id,
                )
                await write_export_archive(
                    backup_path,
                    archive_path,
                    backup_id,
                )
                if claim is not None:
                    claim.commit()
            return archive_path
    except asyncio.CancelledError:
        if archive_path:
            await async_remove_if_exists(archive_path, logger=logger, log_level=logging.DEBUG)
        raise
    except RECOVERABLE_EXCEPTIONS:
        if archive_path:
            await async_remove_if_exists(archive_path, logger=logger, log_level=logging.DEBUG)
        raise
    finally:
        if reservation is not None:
            reservation.release()
