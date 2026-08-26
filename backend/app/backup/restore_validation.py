"""SoAI - Backup restore validation and lock acquisition [backend/app/backup/restore_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.backup_locking import (
    acquire_operations_lock,
    release_operations_lock,
    resolve_backup_path,
)
from app.backup.backup_timeout_settings import get_operations_lock_timeout_seconds
from app.backup.restore_destinations import (
    build_restore_destinations,
    resolve_restore_destination,
)
from app.backup.restore_manifest import load_manifest_for_backup
from app.backup.validated_manifest_entries import build_validated_manifest_entries
from core.backup.manifest import validate_backup_id
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import NotFoundError, SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_islink, async_path_exists
from core.filesystem.size_calculation import get_path_size
from core.logging.protocols import LoggerProtocol
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from filelock import BaseFileLock

    from app.backup.internal_protocols import (
        ConfigProviderProtocol,
        FilesProviderProtocol,
    )
    from core.types.json import JSONDict

__all__ = (
    "RestorePreflightContext",
    "ValidatedRestoreContext",
    "prepare_restore_preflight",
    "validate_and_prepare_restore",
)

OPERATION = "app.backup.restore_validation.validate_and_prepare_restore"


@dataclass(frozen=True, slots=True)
class ValidatedRestoreContext:
    backup_id: str
    backup_path: str
    backups_path: str
    manifest: JSONDict
    restore_required_bytes: int
    snapshot_required_bytes: int
    operations_lock: BaseFileLock


@dataclass(frozen=True, slots=True)
class RestorePreflightContext:
    backup_id: str
    backup_path: str
    manifest: JSONDict
    restore_required_bytes: int
    snapshot_required_bytes: int


async def prepare_restore_preflight(
    *,
    backup_id: str,
    backups_path: str,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    log: LoggerProtocol,
) -> RestorePreflightContext:
    normalized_backup_id = validate_backup_id(backup_id)
    if not backups_path:
        raise StateError("Backups path is not configured.")
    backup_path = resolve_backup_path(backups_path, normalized_backup_id)
    if not await async_isdir(backup_path):
        raise NotFoundError(f"Backup '{normalized_backup_id}' not found.")
    if await async_islink(backup_path):
        raise SecurityError("Refusing to restore from symlinked backup path.")
    manifest = await load_manifest_for_backup(backup_path, log=log)
    if manifest is None:
        raise ValidationError(f"Backup '{normalized_backup_id}' has no valid manifest.")
    validated_entries = build_validated_manifest_entries(manifest.get("files"))
    restore_destinations = build_restore_destinations(config, files)
    snapshot_required_bytes = 0
    restore_required_bytes = 0
    for entry in validated_entries:
        restore_required_bytes += entry.size_bytes
        destination_path = resolve_restore_destination(
            entry.rel_path,
            restore_destinations=restore_destinations,
        )
        if not await async_path_exists(destination_path):
            continue
        destination_size = await get_path_size(destination_path)
        if not is_strict_int(destination_size):
            raise StateError(f"Restore destination size is invalid for {entry.rel_path}.")
        if destination_size < 0:
            raise StateError(f"Restore destination size is negative for {entry.rel_path}.")
        snapshot_required_bytes += destination_size
    return RestorePreflightContext(
        backup_id=normalized_backup_id,
        backup_path=backup_path,
        manifest=manifest,
        restore_required_bytes=restore_required_bytes,
        snapshot_required_bytes=snapshot_required_bytes,
    )


async def validate_and_prepare_restore(
    *,
    backup_id: str,
    backups_path: str,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    log: LoggerProtocol,
) -> ValidatedRestoreContext:
    operations_lock: BaseFileLock | None = None
    if not backups_path:
        raise StateError("Backups path is not configured.")
    operations_lock = await acquire_operations_lock(
        backups_path,
        timeout_seconds=get_operations_lock_timeout_seconds(config),
    )
    try:
        preflight = await prepare_restore_preflight(
            backup_id=backup_id,
            backups_path=backups_path,
            config=config,
            files=files,
            log=log,
        )
    except (NotFoundError, SecurityError, StateError, ValidationError):
        if operations_lock is not None:
            await release_operations_lock(operations_lock, log=log)
        raise
    except asyncio.CancelledError:
        if operations_lock is not None:
            await release_operations_lock(operations_lock, log=log)
        raise
    except RECOVERABLE_EXCEPTIONS as exception:
        if operations_lock is not None:
            await release_operations_lock(operations_lock, log=log)
        coerced = coerce_to_soai_error(
            exception,
            operation="app.backup.restore_validation.validate_and_prepare_restore",
        )
        log_exception(
            log,
            coerced,
            message="Unhandled exception during restore validation",
            operation=OPERATION,
        )
        if coerced is exception:
            raise
        raise coerced from exception

    return ValidatedRestoreContext(
        backup_id=preflight.backup_id,
        backup_path=preflight.backup_path,
        backups_path=backups_path,
        manifest=preflight.manifest,
        restore_required_bytes=preflight.restore_required_bytes,
        snapshot_required_bytes=preflight.snapshot_required_bytes,
        operations_lock=operations_lock,
    )
