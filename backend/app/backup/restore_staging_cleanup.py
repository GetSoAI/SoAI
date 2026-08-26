"""SoAI - Restore staging artifact cleanup [backend/app/backup/restore_staging_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.stale_artifact_scanning import sync_collect_stale_paths_by_mtime
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.epoch import epoch_seconds_float

__all__ = ("cleanup_stale_restore_staging_artifacts",)

OPERATION_APP_BACKUP_RESTORE_STAGING_CLEANUP_SCAN = "app.backup.restore_staging_cleanup.scan"
OPERATION_APP_BACKUP_RESTORE_STAGING_CLEANUP_REMOVE = "app.backup.restore_staging_cleanup.remove"

_STAGING_PREFIX = ".soai_restore_staging."
_DEFAULT_MAX_STAGING_AGE_SECONDS = 21_600


def _is_restore_staging_entry(entry: os.DirEntry[str]) -> bool:
    return entry.name.startswith(_STAGING_PREFIX)


def _resolve_parent_directories(
    backups_path: str,
    restore_destinations: dict[str, str] | None,
) -> list[str]:
    parents: set[str] = set()
    if isinstance(backups_path, str) and backups_path.strip():
        parents.add(os.path.realpath(str(backups_path)))
    if restore_destinations:
        for destination in restore_destinations.values():
            if not isinstance(destination, str) or not destination.strip():
                continue
            parents.add(os.path.realpath(os.path.dirname(destination)))
    return sorted(parent for parent in parents if parent)


async def cleanup_stale_restore_staging_artifacts(
    *,
    backups_path: str,
    restore_destinations: dict[str, str] | None,
    max_age_seconds: float | None = None,
    log: LoggerProtocol,
) -> None:
    if not isinstance(backups_path, str) or not backups_path.strip():
        raise ValidationError("backups_path is required.")
    max_age = (
        float(max_age_seconds)
        if max_age_seconds is not None
        else float(_DEFAULT_MAX_STAGING_AGE_SECONDS)
    )
    if max_age <= 0:
        raise ValidationError("max_age_seconds must be positive.")
    parents = _resolve_parent_directories(backups_path, restore_destinations)
    if not parents:
        return
    now = epoch_seconds_float()
    for parent in parents:
        try:
            stale_paths = await asyncio.to_thread(
                sync_collect_stale_paths_by_mtime,
                parent,
                now_seconds=now,
                max_age_seconds=max_age,
                include_entry=_is_restore_staging_entry,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Failed to scan for stale restore staging artifacts",
                operation=OPERATION_APP_BACKUP_RESTORE_STAGING_CLEANUP_SCAN,
                details={"parent": parent},
                level="warning",
            )
            continue
        for stale_path in stale_paths:
            try:
                await run_joined_thread_call(
                    sync_remove_tree_no_symlinks,
                    stale_path,
                    task_name="backup-restore-stale-staging-remove",
                )
                log.debug("Removed stale restore staging artifact at %s", stale_path)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    log,
                    exception,
                    message="Failed to remove stale restore staging artifact",
                    operation=OPERATION_APP_BACKUP_RESTORE_STAGING_CLEANUP_REMOVE,
                    details={"path": stale_path, "parent": parent},
                    level="warning",
                )
