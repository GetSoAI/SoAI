"""SoAI - Backup retention policy enforcement and listing [backend/app/backup/backup_retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import re
from typing import TYPE_CHECKING

from app.backup.archive_io import coerce_manifest_timestamp_ms, read_manifest_file
from app.backup.backup_removal import sync_remove_tree_no_symlinks
from app.backup.backup_timeout_settings import get_orphan_age_threshold_hours
from app.backup.internal_protocols import ConfigProviderProtocol
from app.backup.licensing_recovery import licensing_recovery_is_restorable
from core.backup.manifest import BACKUP_ID_REGEX
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.async_queries import async_isdir, async_islink, async_path_exists
from core.logging.protocols import LoggerProtocol
from core.logging.trace import get_logger
from core.timing.durations import hours_to_ms
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "apply_retention_policy",
    "is_symlink_with_warning",
    "list_completed_backups",
    "list_orphaned_backup_directories",
)

LOGGER_NAME = "SoAI.app.backup.backup_retention"
OPERATION_UTILS_BACKUP_APPLY_RETENTION_POLICY = "utils_backup.apply_retention_policy"
OPERATION_UTILS_BACKUP_LIST_COMPLETED_BACKUPS = "utils_backup.list_completed_backups"
OPERATION_UTILS_BACKUP_LIST_ORPHANED_BACKUP_DIRECTORIES = (
    "utils_backup.list_orphaned_backup_directories"
)


async def list_completed_backups(
    *,
    backups_path: str,
    restorable_only: bool = False,
) -> list[tuple[str, int, JSONDict]]:
    logger = get_logger(LOGGER_NAME)
    result: list[tuple[str, int, JSONDict]] = []
    if not isinstance(backups_path, str) or not backups_path.strip():
        return result
    entries = await asyncio.to_thread(os.listdir, backups_path)
    for entry in entries:
        if entry.endswith(".part"):
            continue
        if re.fullmatch(BACKUP_ID_REGEX, entry) is None:
            continue
        backup_path = os.path.join(backups_path, entry)
        if not await async_isdir(backup_path):
            continue
        if await async_islink(backup_path):
            continue
        manifest_path = os.path.join(backup_path, "manifest.json")
        if not await async_path_exists(manifest_path):
            continue
        try:
            manifest = await asyncio.to_thread(read_manifest_file, manifest_path)
            restorable = licensing_recovery_is_restorable(manifest.get("licensing_recovery"))
            if restorable_only and not restorable:
                continue
            timestamp_ms = await asyncio.to_thread(
                coerce_manifest_timestamp_ms,
                manifest,
                backup_path,
            )
            result.append((backup_path, timestamp_ms, manifest))
        except (
            OSError,
            ValidationError,
        ) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to read backup manifest; excluding backup from completed listing (non-critical).",
                operation=OPERATION_UTILS_BACKUP_LIST_COMPLETED_BACKUPS,
                details={"backup_path": backup_path},
                level="debug",
            )
    return result


async def list_orphaned_backup_directories(
    *,
    backups_path: str,
) -> list[tuple[str, int]]:
    logger = get_logger(LOGGER_NAME)
    orphaned: list[tuple[str, int]] = []
    if not isinstance(backups_path, str) or not backups_path.strip():
        return orphaned
    entries = await asyncio.to_thread(os.listdir, backups_path)
    for entry in entries:
        if entry.endswith(".part"):
            continue
        if re.fullmatch(BACKUP_ID_REGEX, entry) is None:
            continue
        backup_path = os.path.join(backups_path, entry)
        if not await async_isdir(backup_path):
            continue
        if await async_islink(backup_path):
            continue
        manifest_path = os.path.join(backup_path, "manifest.json")
        try:
            if await async_path_exists(manifest_path):
                await asyncio.to_thread(read_manifest_file, manifest_path)
                continue
            stat_info = await asyncio.to_thread(os.lstat, backup_path)
            orphaned.append((backup_path, int(stat_info.st_mtime_ns // 1_000_000)))
        except (
            OSError,
            ValidationError,
        ) as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to inspect backup directory candidate for orphan cleanup (non-critical).",
                operation=OPERATION_UTILS_BACKUP_LIST_ORPHANED_BACKUP_DIRECTORIES,
                details={"backup_path": backup_path},
                level="debug",
            )
            try:
                stat_info = await asyncio.to_thread(os.lstat, backup_path)
                orphaned.append((backup_path, int(stat_info.st_mtime_ns // 1_000_000)))
            except OSError as stat_exception:
                log_exception(
                    logger,
                    stat_exception,
                    message="Failed to stat orphaned backup directory candidate.",
                    operation=OPERATION_UTILS_BACKUP_LIST_ORPHANED_BACKUP_DIRECTORIES,
                    details={"backup_path": backup_path},
                    level="warning",
                )
    return orphaned


async def is_symlink_with_warning(path: str, *, context: str, log: LoggerProtocol) -> bool:
    if not isinstance(path, str) or not path.strip():
        raise ValidationError("path is required.")
    if await async_islink(path):
        log.warning(
            "Skipping symlink during %s: %s",
            context,
            os.path.basename(path),
        )
        return True
    return False


async def apply_retention_policy(
    *,
    backups_path: str,
    config: ConfigProviderProtocol,
    log: LoggerProtocol,
) -> None:
    if not await async_isdir(backups_path):
        return
    max_backups = config.get("DATA.BACKUP.RETENTION.MAX_BACKUPS", 7)
    if not is_strict_int(max_backups) or max_backups < 1:
        raise ValidationError("DATA.BACKUP.RETENTION.MAX_BACKUPS must be a positive integer.")
    max_age_hours = config.get("DATA.BACKUP.RETENTION.MAX_AGE_HOURS", 720)
    if (
        not isinstance(max_age_hours, int | float)
        or isinstance(max_age_hours, bool)
        or max_age_hours < 0
    ):
        raise ValidationError("DATA.BACKUP.RETENTION.MAX_AGE_HOURS must be a non-negative number.")
    backups = await list_completed_backups(backups_path=backups_path)
    if not backups:
        log.debug("Retention policy: no backups found")
        return
    backups.sort(key=lambda item: item[1], reverse=True)
    log.debug(
        "Retention policy: found %s backups, max_backups=%s, max_age_hours=%s",
        len(backups),
        max_backups,
        max_age_hours,
    )
    now_ms = epoch_ms()
    deletions: list[tuple[str, str]] = []
    expired_paths: set[str] = set()
    if max_age_hours > 0:
        max_age_ms = hours_to_ms(float(max_age_hours))
        expired = [(path, ts) for path, ts, _manifest in backups if (now_ms - ts) > max_age_ms]
        expired.sort(key=lambda item: item[1])
        for backup_path, _ts in expired:
            expired_paths.add(backup_path)
            deletions.append((backup_path, "expired"))
    remaining = [backup for backup in backups if backup[0] not in expired_paths]
    if len(remaining) > max_backups:
        retained_paths = {backup[0] for backup in remaining[:max_backups]}
        if not any(
            licensing_recovery_is_restorable(backup[2].get("licensing_recovery"))
            for backup in remaining
            if backup[0] in retained_paths
        ):
            newest_restorable = next(
                (
                    backup
                    for backup in remaining[max_backups:]
                    if licensing_recovery_is_restorable(backup[2].get("licensing_recovery"))
                ),
                None,
            )
            if newest_restorable is not None:
                retained_paths.remove(remaining[max_backups - 1][0])
                retained_paths.add(newest_restorable[0])
        for backup_path, _timestamp, _manifest in remaining:
            if backup_path in retained_paths:
                continue
            deletions.append((backup_path, "excess"))
    for backup_path, reason in deletions:
        if await is_symlink_with_warning(
            backup_path,
            context=f"retention {reason} cleanup",
            log=log,
        ):
            continue
        try:
            await run_joined_thread_call(
                sync_remove_tree_no_symlinks,
                backup_path,
                task_name="backup-retention-remove",
            )
            if reason == "expired":
                log.info(
                    "Deleted expired backup (age > %sh): %s",
                    max_age_hours,
                    os.path.basename(backup_path),
                )
            else:
                log.info(
                    "Deleted excess backup (count > %s): %s",
                    max_backups,
                    os.path.basename(backup_path),
                )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message=f"Failed to delete {reason} backup",
                operation=OPERATION_UTILS_BACKUP_APPLY_RETENTION_POLICY,
                details={"path": backup_path, "reason": reason},
                level="warning",
            )
    orphaned_directories = await list_orphaned_backup_directories(backups_path=backups_path)
    if not orphaned_directories:
        return
    orphan_age_threshold_hours = get_orphan_age_threshold_hours(config)
    orphan_age_threshold_ms = hours_to_ms(float(orphan_age_threshold_hours))
    for orphan_path, orphan_mtime_ms in orphaned_directories:
        orphan_age_ms = now_ms - orphan_mtime_ms
        if orphan_age_ms <= orphan_age_threshold_ms:
            log.warning(
                "Found orphaned backup directory (missing manifest): %s",
                os.path.basename(orphan_path),
            )
            continue
        if await is_symlink_with_warning(orphan_path, context="orphan cleanup", log=log):
            continue
        try:
            await run_joined_thread_call(
                sync_remove_tree_no_symlinks,
                orphan_path,
                task_name="backup-retention-orphan-remove",
            )
            display_hours = (
                int(orphan_age_threshold_hours)
                if orphan_age_threshold_hours == int(orphan_age_threshold_hours)
                else orphan_age_threshold_hours
            )
            log.info(
                "Deleted orphaned backup directory (age > %sh, missing manifest): %s",
                display_hours,
                os.path.basename(orphan_path),
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Failed to delete orphaned backup directory",
                operation=OPERATION_UTILS_BACKUP_APPLY_RETENTION_POLICY,
                details={"path": orphan_path},
                level="warning",
            )
