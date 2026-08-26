"""SoAI - Backup service lifecycle operations [backend/app/backup/lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.backup.backup_creation import cleanup_stale_parts
from app.backup.backup_marker_ops import (
    clear_initial_backup_marker,
    update_initial_backup_marker,
)
from app.backup.backup_marker_state import load_initial_backup_marker_state
from app.backup.backup_recursion import is_backup_recursion_safe
from app.backup.backup_root_setup import prepare_backup_root
from app.backup.backup_schedule import run_backup_loop
from app.backup.backup_schedule_settings import resolve_backup_schedule_settings
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.formatting.time import format_interval_hours
from core.logging.protocols import LoggerProtocol
from core.runtime.platform import get_runtime_platform
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC

if TYPE_CHECKING:
    from app.backup.internal_protocols import (
        BackupScheduleContext,
        BackupServiceContext,
        ConfigProviderProtocol,
        FilesProviderProtocol,
    )

__all__ = (
    "InitializationResult",
    "execute_initialization",
    "execute_shutdown",
    "execute_startup",
)

OPERATION_APPLICATION_BACKUP_INITIALIZE_RESOLVE_PATH_DISABLED = (
    "application_backup.initialize.resolve_path_disabled"
)
OPERATION_APPLICATION_BACKUP_START = "application_backup.start"


@dataclass(frozen=True, slots=True)
class InitializationResult:
    backups_path: str
    backup_interval_hours: float | None
    run_on_startup: bool
    initialized: bool


async def execute_initialization(
    enabled: bool,
    get_backups_path: str,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    context: BackupServiceContext,
    log: LoggerProtocol,
) -> InitializationResult:
    if not enabled:
        try:
            await clear_initial_backup_marker(get_backups_path, log=log)
        except RECOVERABLE_EXCEPTIONS as path_exception:
            log_handled_exception(
                log,
                path_exception,
                message="Could not resolve backup path for marker cleanup while disabled (non-critical).",
                operation=OPERATION_APPLICATION_BACKUP_INITIALIZE_RESOLVE_PATH_DISABLED,
                level="debug",
            )
        log.info("ApplicationBackupService is disabled via configuration.")
        return InitializationResult(
            backups_path="",
            backup_interval_hours=None,
            run_on_startup=False,
            initialized=False,
        )
    if not await is_backup_recursion_safe(get_backups_path, config, files):
        log.warning(
            "Backup path '%s' is inside a directory that would be backed up. This would cause infinite recursion. ApplicationBackupService is disabled.",
            get_backups_path,
        )
        return InitializationResult(
            backups_path="",
            backup_interval_hours=None,
            run_on_startup=False,
            initialized=False,
        )
    runtime_platform = get_runtime_platform()
    await prepare_backup_root(
        get_backups_path,
        is_windows=runtime_platform.is_windows,
        log=log,
    )
    await cleanup_stale_parts(context, backups_path=get_backups_path)
    interval_hours, run_on_startup = resolve_backup_schedule_settings(config)
    interval_str = format_interval_hours(interval_hours) if interval_hours else "disabled"
    log.info(
        "ApplicationBackupService initialized. Backups path: %s, interval: %s",
        get_backups_path,
        interval_str,
    )
    return InitializationResult(
        backups_path=get_backups_path,
        backup_interval_hours=interval_hours,
        run_on_startup=run_on_startup,
        initialized=True,
    )


async def execute_startup(
    context: BackupScheduleContext,
    backups_path: str,
    run_on_startup: bool,
    backup_interval_hours: float | None,
    config: ConfigProviderProtocol,
    log: LoggerProtocol,
    wait_for_startup_ready: bool = True,
) -> asyncio.Task[None] | None:
    runtime_platform = get_runtime_platform()
    marker_path, previously_completed, all_targets_previously_completed = (
        await load_initial_backup_marker_state(backups_path, config)
    )
    if not all_targets_previously_completed:
        log.info("Running initial backup after enabling backup feature...")
        try:
            result = await context.create_backup()
            manifest_value = result.get("manifest")
            if isinstance(manifest_value, dict):
                targets_completed = manifest_value.get("targets_completed", {})
                if isinstance(targets_completed, dict):
                    await update_initial_backup_marker(
                        backups_path=backups_path,
                        marker_path=marker_path,
                        previous_completed=previously_completed,
                        targets_completed=targets_completed,
                        is_windows=runtime_platform.is_windows,
                        log=log,
                    )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Initial backup failed",
                operation=OPERATION_APPLICATION_BACKUP_START,
            )
    elif run_on_startup:
        log.info("Running startup backup...")
        try:
            await context.create_backup()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                log,
                exception,
                message="Startup backup failed",
                operation=OPERATION_APPLICATION_BACKUP_START,
            )
    if backup_interval_hours is not None and backup_interval_hours > 0:
        return create_ephemeral_task(
            run_backup_loop(context, wait_for_startup_ready=wait_for_startup_ready),
            name="backup-periodic",
        )
    return None


async def execute_shutdown(
    backup_shutdown_event: asyncio.Event | None,
    backup_task: asyncio.Task[None] | None,
    operation_tasks: set[asyncio.Task[None]],
    log: LoggerProtocol,
) -> None:
    if backup_shutdown_event:
        backup_shutdown_event.set()
    if backup_task and not backup_task.done():
        try:
            await asyncio.wait_for(backup_task, timeout=RESPONSIVE_TIMEOUT_SEC)
        except TimeoutError:
            log.warning("Backup task did not stop in time, cancelling.")
            backup_task.cancel()
            try:
                await backup_task
            except asyncio.CancelledError:
                log.debug("Backup task cancelled successfully.")
    pending_tasks = list(operation_tasks)
    operation_tasks.clear()
    await cancel_and_await(
        pending_tasks,
        logger=log,
        task_label="backup/restore operations",
        message="Cancelling active backup/restore operations...",
        log_level=logging.WARNING,
    )
    log.debug("ApplicationBackupService shut down.")
