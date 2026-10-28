"""SoAI - Backup restore manifest helpers [backend/app/backup/restore_manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.backup.archive_io import read_manifest_file
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError, ValidationError
from core.filesystem.async_queries import async_isdir, async_path_exists
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("load_manifest_for_backup",)

OPERATION = "application_restore.load_manifest_for_backup"


async def load_manifest_for_backup(
    backup_path: str,
    *,
    log: LoggerProtocol,
) -> JSONDict | None:
    if not backup_path or not await async_isdir(backup_path):
        return None
    manifest_path = os.path.join(backup_path, "manifest.json")
    if not await async_path_exists(manifest_path):
        return None
    try:
        return await asyncio.to_thread(read_manifest_file, manifest_path)
    except ValidationError as exception:
        raise ValidationError(
            "Backup manifest is not valid JSON.",
            details={"backup_path": backup_path, "manifest_path": manifest_path},
        ) from exception
    except OSError as exception:
        log_exception(
            log,
            exception,
            message="Failed to load backup manifest.",
            operation=OPERATION,
            details={"backup_path": backup_path, "manifest_path": manifest_path},
        )
        raise StateError(
            "Failed to read backup manifest.",
            details={"backup_path": backup_path, "manifest_path": manifest_path},
        ) from exception
