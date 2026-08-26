"""SoAI - Backup verification helpers [backend/app/backup/backup_verification.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from app.backup.archive_io import read_manifest_file
from app.backup.backup_locking import (
    acquire_operations_lock,
    release_operations_lock,
    resolve_backup_path,
)
from app.backup.backup_timeout_settings import get_operations_lock_timeout_seconds
from app.backup.copy_no_symlinks.file_copy import sync_copy_file_and_hash_no_symlinks
from app.backup.copy_no_symlinks.tree_hashing import sync_hash_directory_no_symlinks
from app.backup.internal_protocols import BackupServiceContext
from app.backup.task_item_progress import report_task_item_progress
from app.backup.validated_manifest_entries import build_validated_manifest_entries
from core.backup.manifest import validate_backup_id
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import NotFoundError, SecurityError, StateError
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_islink, async_path_exists
from core.logging.trace import get_logger

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("verify_backup",)

LOGGER_NAME = "SoAI.app.backup.backup_verification"
OPERATION = "app.backup.verify_backup.verify_item"
OPERATION_PUBLISH = "app.backup.verify_backup.publish_event"


async def verify_backup(
    self: BackupServiceContext,
    backup_id: str,
    *,
    task_id: str,
    user_id: int,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    self.require_operational()
    normalized_backup_id = validate_backup_id(backup_id)
    if not self.backups_path:
        raise StateError("Backups path is not configured.")
    operations_lock = await acquire_operations_lock(
        self.backups_path,
        timeout_seconds=get_operations_lock_timeout_seconds(self.config),
    )
    try:
        backup_path = resolve_backup_path(self.backups_path, normalized_backup_id)
        if not await async_isdir(backup_path):
            raise NotFoundError(
                f"Backup '{normalized_backup_id}' not found.",
                details={"backup_id": normalized_backup_id},
            )
        if await async_islink(backup_path):
            raise SecurityError(
                "Refusing to verify symlinked backup path.",
                details={"backup_id": normalized_backup_id},
            )
        manifest_path = os.path.join(backup_path, "manifest.json")
        if not await async_path_exists(manifest_path):
            raise NotFoundError(
                f"Backup '{normalized_backup_id}' is missing manifest.json.",
                details={"backup_id": normalized_backup_id},
            )
        manifest = await asyncio.to_thread(read_manifest_file, manifest_path)
        validated_entries = build_validated_manifest_entries(manifest.get("files"))
        total = len(validated_entries)
        verified_files: list[str] = []
        errors: list[JSONDict] = []
        for index, entry in enumerate(validated_entries, start=1):
            rel_path = entry.rel_path
            source_item_path = os.path.join(backup_path, rel_path)
            if not await async_path_exists(source_item_path):
                errors.append({"path": rel_path, "error": "Missing item"})
            else:
                try:
                    if entry.entry_type == "file":
                        actual_size, actual_hash = await asyncio.to_thread(
                            sync_copy_file_and_hash_no_symlinks,
                            source_item_path,
                            None,
                        )
                    else:
                        actual_size, actual_hash = await asyncio.to_thread(
                            sync_hash_directory_no_symlinks,
                            source_item_path,
                        )
                    if actual_size != entry.size_bytes:
                        raise SecurityError(f"Verify size mismatch for {rel_path}.")
                    if actual_hash != entry.sha256_hash:
                        raise SecurityError(f"Verify hash mismatch for {rel_path}.")
                    verified_files.append(rel_path)
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Backup verification failed for item (non-critical).",
                        operation=OPERATION,
                        details={"rel_path": rel_path},
                        level="debug",
                    )
                    errors.append(
                        {
                            "path": rel_path,
                            "error": project_public_exception(exception).message,
                        }
                    )

            percent = min(99, max(1, int(index / max(1, total) * 99)))
            await report_task_item_progress(
                event_bus=self.runtime_dependencies.event_bus,
                registry=self.runtime_dependencies.task_registry,
                task_id=task_id,
                user_id=user_id,
                percent=percent,
                rel_path=rel_path,
                event_message="Verified item",
                status_message=f"Verified {rel_path}",
                log=logger,
                publish_operation=OPERATION_PUBLISH,
                publish_failure_message="Failed to publish backup verification progress event.",
                publish_details={"task_id": str(task_id), "backup_id": normalized_backup_id},
                progress_operation=OPERATION_PUBLISH,
                progress_failure_message="Failed to update backup verification progress.",
            )

        success = not errors
        return {
            "backup_id": normalized_backup_id,
            "files_verified": verified_files,
            "errors": errors,
            "success": success,
        }
    finally:
        await release_operations_lock(operations_lock, log=logger)
