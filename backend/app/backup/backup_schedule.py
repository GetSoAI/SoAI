"""SoAI - Backup scheduling helpers [backend/app/backup/backup_schedule.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.backup.backup_retention import list_completed_backups
from app.backup.backup_timeout_settings import (
    get_backup_retry_base_seconds,
    get_backup_retry_max_seconds,
)
from app.backup.internal_protocols import (
    BackupRuntimeDependenciesProtocol,
    BackupScheduleContext,
    ConfigProviderProtocol,
)
from app.backup.task_create import run_create_backup_task
from app.backup.task_registry_reporting import update_status_noncritical
from core.concurrency.context import create_system_cancellation_id
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.shutdown_waits import wait_for_shutdown_or_schedule_change
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.filesystem.async_queries import async_isdir
from core.formatting.time import format_duration_hhmm
from core.logging.trace import get_logger
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.type_catalog import TASK_TYPE_BACKUP_CREATE
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from core.timing.durations import hours_to_ms
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds

__all__ = (
    "load_last_backup_timestamp_from_disk",
    "run_backup_loop",
)

LOGGER_NAME = "SoAI.app.backup.backup_schedule"
OPERATION_APPLICATION_BACKUP_LOAD_LAST_BACKUP_TIMESTAMP_FROM_DISK = (
    "application_backup.load_last_backup_timestamp_from_disk"
)
OPERATION_APPLICATION_BACKUP_RUN_BACKUP_LOOP = "application_backup.run_backup_loop"


async def load_last_backup_timestamp_from_disk(
    self: BackupScheduleContext,
) -> int | None:
    logger = get_logger(LOGGER_NAME)
    if not self.backups_path or not await async_isdir(self.backups_path):
        return None
    try:
        backups = await list_completed_backups(
            backups_path=self.backups_path,
            restorable_only=True,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to load last backup timestamp from disk (non-critical).",
            operation=OPERATION_APPLICATION_BACKUP_LOAD_LAST_BACKUP_TIMESTAMP_FROM_DISK,
            details={"backups_path": self.backups_path},
            level="debug",
        )
        return None
    if not backups:
        return None
    return max((timestamp_ms for _, timestamp_ms, _ in backups))


async def run_backup_loop(
    self: BackupScheduleContext,
    *,
    wait_for_startup_ready: bool = True,
) -> None:
    logger = get_logger(LOGGER_NAME)
    context: BackupScheduleContext = self
    runtime_dependencies: BackupRuntimeDependenciesProtocol = context.runtime_dependencies
    config_provider: ConfigProviderProtocol = context.config
    interval_hours = self.backup_interval_hours
    if interval_hours is None:
        logger.warning("Backup loop started with no interval configured. Exiting.")
        return
    interval_ms = hours_to_ms(float(interval_hours))
    if wait_for_startup_ready and self.startup_ready_event:
        logger.debug("Backup task waiting for SoAI startup to complete...")
        startup_wait_task: asyncio.Task[bool] = create_ephemeral_task(
            self.startup_ready_event.wait(),
            name="backup-startup-wait",
        )
        shutdown_wait_task: asyncio.Task[bool] | None = None
        if self.backup_shutdown_event:
            shutdown_wait_task = create_ephemeral_task(
                self.backup_shutdown_event.wait(),
                name="backup-shutdown-wait",
            )
        wait_tasks: set[asyncio.Task[bool]] = {startup_wait_task}
        if shutdown_wait_task:
            wait_tasks.add(shutdown_wait_task)
        try:
            while True:
                done, pending = await asyncio.wait(
                    wait_tasks,
                    timeout=LOCAL_IO_TIMEOUT_SEC,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if done:
                    break
        except asyncio.CancelledError:
            logger.debug("Backup task cancelled while waiting for startup.")
            for pending_task in (startup_wait_task, shutdown_wait_task):
                if pending_task and not pending_task.done():
                    pending_task.cancel()
            return
        for pending_task in pending:
            pending_task.cancel()
            try:
                await pending_task
            except asyncio.CancelledError:
                logger.debug(
                    "Pending task %s cancelled during backup loop cleanup",
                    pending_task.get_name(),
                )
        if shutdown_wait_task and shutdown_wait_task in done:
            logger.debug("Backup task received shutdown signal during startup wait.")
            return
        logger.debug("SoAI startup complete, backup task now active.")
    last_backup_timestamp_ms = self.last_backup_timestamp_ms
    if last_backup_timestamp_ms is None:
        loaded_timestamp = await load_last_backup_timestamp_from_disk(self)
        if loaded_timestamp is not None:
            self.record_backup_timestamp_ms(loaded_timestamp)
        last_backup_timestamp_ms = loaded_timestamp
    last_success_ts_ms = (
        int(last_backup_timestamp_ms) if last_backup_timestamp_ms is not None else epoch_ms()
    )
    next_run_ts_ms = last_success_ts_ms + interval_ms
    consecutive_failures = 0
    while self.backup_shutdown_event and not self.backup_shutdown_event.is_set():
        try:
            if self.backup_schedule_changed_event and self.backup_schedule_changed_event.is_set():
                self.backup_schedule_changed_event.clear()
                if self.last_backup_timestamp_ms is not None:
                    last_success_ts_ms = int(self.last_backup_timestamp_ms)
                    next_run_ts_ms = last_success_ts_ms + interval_ms
                    consecutive_failures = 0
            delay_sec = max(0.0, (next_run_ts_ms - epoch_ms()) / 1000.0)
            if delay_sec > 0:
                wait_reason = await wait_for_shutdown_or_schedule_change(
                    self.backup_shutdown_event,
                    self.backup_schedule_changed_event,
                    delay_sec,
                )
                if wait_reason == "shutdown":
                    break
                if wait_reason == "schedule_changed":
                    continue
                if self.backup_shutdown_event.is_set():
                    break
            logger.info("Starting scheduled backup...")
            registry = runtime_dependencies.task_registry
            task = await create(
                registry,
                task_type=TASK_TYPE_BACKUP_CREATE,
                user_id=0,
                owner_id="backup_service",
                owner_type="system",
                cancellation_id=create_system_cancellation_id("scheduled_backup"),
                progress_total=100,
                metadata={"operation": "scheduled_backup"},
            )
            await update_status_noncritical(
                registry=registry,
                task_id=task.task_id,
                new_status=TaskStatus.WORKING,
                log=logger,
                operation=OPERATION_APPLICATION_BACKUP_RUN_BACKUP_LOOP,
                message="Failed to update scheduled backup task status.",
                status_message="Scheduled backup started",
                level="debug",
            )
            operation_task = spawn_tracked_task(
                run_create_backup_task(
                    context,
                    task.task_id,
                    user_id=0,
                    operation="scheduled_backup",
                ),
                name=f"backup-scheduled-create-{task.task_id}",
                logger=logger,
                cancellation_binder=runtime_dependencies.task_cancellation_binder,
                cancellation_id=task.cancellation_id,
                owner="backup_scheduled_create",
                finalizer_tracker=runtime_dependencies.task_finalizer_tracker,
            )
            backup_ok = await operation_task
            if backup_ok:
                consecutive_failures = 0
                if self.last_backup_timestamp_ms is not None:
                    last_success_ts_ms = int(self.last_backup_timestamp_ms)
                next_run_ts_ms = last_success_ts_ms + interval_ms
                continue
            consecutive_failures += 1
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Scheduled backup task iteration failed (non-critical).",
                operation=OPERATION_APPLICATION_BACKUP_RUN_BACKUP_LOOP,
                level="warning",
            )
            consecutive_failures += 1
        except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="application_backup.run_backup_loop",
            )
            log_handled_exception(
                logger,
                coerced,
                message="Scheduled backup task iteration failed unexpectedly (non-critical).",
                operation=OPERATION_APPLICATION_BACKUP_RUN_BACKUP_LOOP,
                level="error",
            )
            consecutive_failures += 1
        retry_base = get_backup_retry_base_seconds(config_provider)
        retry_max = get_backup_retry_max_seconds(config_provider)
        retry_delay = compute_exponential_backoff_seconds(
            consecutive_failures - 1,
            base_seconds=retry_base,
            maximum_seconds=retry_max,
        )
        next_run_ts_ms = epoch_ms() + int(retry_delay * 1000)
        logger.warning(
            "Scheduled backup failed; retrying in %s (attempt %s).",
            format_duration_hhmm(retry_delay),
            consecutive_failures,
        )
    logger.debug("Backup task stopped.")
