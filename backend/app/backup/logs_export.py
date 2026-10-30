"""SoAI - Logs export preparation and resource ownership [backend/app/backup/logs_export.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import sys
from functools import partial
from threading import Event

from app.backup.backup_target_paths import resolve_required_path
from app.backup.backup_target_paths_extra import get_logs_path
from app.backup.internal_protocols import ConfigProviderProtocol, FilesProviderProtocol
from app.backup.logs_export_capture import capture_logs, inventory_logs
from app.backup.logs_export_failures import logs_export_failure, project_logs_export_failure
from app.backup.logs_export_selection import resolve_logs_export_file_paths
from core.archives.resource_limits import ArchivePlanningBudget, default_archive_resource_limits
from core.archives.zip_creation_models import ZipArchiveResult
from core.archives.zip_writing import remove_completed_zip_archive, write_zip_archive
from core.concurrency.bounded_blocking import BoundedBlockingPool
from core.concurrency.cancellation import TaskCancelledError, check_cancellation_deadline
from core.concurrency.cancellation_cleanup import (
    wait_for_task_completion,
)
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    SecurityError,
    StateError,
)
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.file_identity import FileIdentity
from core.files.managed_path_access import stat_managed_path
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.path_policy import is_path_inside_directory, is_path_within_base, is_same_path
from core.files.temp_directory_scope import (
    create_scoped_temp_directory,
    remove_scoped_temp_directory,
)
from core.hardware.protocols_storage import StorageManagerProtocol
from core.hardware.reservation_claims import claim_reserved_write
from core.hardware.reservation_exceptions import preserve_primary_exception_cleanup_failure
from core.logging.trace import get_logger
from core.meta.version import __version__
from core.timing.constants import LONG_REQUEST_TIMEOUT_SEC
from core.timing.formatting import datetime_to_utc_iso, utc_now

__all__ = ("create_logs_export_archive",)

LOGGER_NAME = "SoAI.app.backup.logs_export"
OPERATION_LOGS_EXPORT_CLEANUP = "logs.export.cleanup"


async def create_logs_export_archive(
    *,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    storage_manager: StorageManagerProtocol,
    pool: BoundedBlockingPool,
    cancellation_event: Event,
    preparations: dict[asyncio.Task[ZipArchiveResult], Event],
) -> ZipArchiveResult:
    deadline = deadline_after(LONG_REQUEST_TIMEOUT_SEC)
    task = create_ephemeral_task(
        _run_logs_export_preparation(
            config=config,
            files=files,
            storage_manager=storage_manager,
            pool=pool,
            cancellation_event=cancellation_event,
            deadline=deadline,
        ),
        name="logs-export",
        log_exceptions=False,
    )
    preparations[task] = cancellation_event
    try:
        return await task
    except asyncio.CancelledError as exception:
        cancellation_event.set()
        task.cancel()
        await wait_for_task_completion(task, retain_resources_until_complete=True)
        if not task.cancelled() and task.exception() is None:
            try:
                await run_joined_thread_call(
                    remove_completed_zip_archive,
                    task.result(),
                    task_name="logs-export-service-cleanup",
                    retain_resources_until_complete=True,
                )
            except OSError as cleanup_exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_exception,
                    message="Logs export cleanup failed.",
                    operation=OPERATION_LOGS_EXPORT_CLEANUP,
                )
                preserve_primary_exception_cleanup_failure(
                    exception, cleanup_exception, cleanup_action="Completed logs export cleanup"
                )
        raise
    finally:
        preparations.pop(task, None)


async def _run_logs_export_preparation(
    *,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    storage_manager: StorageManagerProtocol,
    pool: BoundedBlockingPool,
    cancellation_event: Event,
    deadline: MonotonicDeadline,
) -> ZipArchiveResult:
    completed_results: list[ZipArchiveResult] = []
    try:
        check_cancellation_deadline(cancellation_event, deadline, operation="logs.export")
        return await run_joined_thread_call(
            partial(
                _prepare_logs_export,
                config=config,
                files=files,
                storage_manager=storage_manager,
                cancellation_event=cancellation_event,
                deadline=deadline,
            ),
            task_name="logs-export-prepare",
            pool=pool,
            admission_deadline=deadline,
            retain_resources_until_complete=True,
            on_cancel=cancellation_event.set,
            cancelled_result_cleanup=completed_results.append,
        )
    except TaskCancelledError as exception:
        raise asyncio.CancelledError() from exception
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        projected = project_logs_export_failure(exception)
        if projected is exception:
            raise
        raise projected from exception
    finally:
        primary_exception = sys.exception()
        for result in completed_results:
            try:
                await run_joined_thread_call(
                    remove_completed_zip_archive,
                    result,
                    task_name="logs-export-cancelled-result",
                    retain_resources_until_complete=True,
                )
            except OSError as cleanup_exception:
                log_exception(
                    get_logger(LOGGER_NAME),
                    cleanup_exception,
                    message="Logs export cleanup failed.",
                    operation=OPERATION_LOGS_EXPORT_CLEANUP,
                )
                preserve_primary_exception_cleanup_failure(
                    primary_exception,
                    cleanup_exception,
                    cleanup_action="Cancelled logs export cleanup",
                )


def _resolve_logs_export_paths(
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
) -> tuple[str, str, str, FileIdentity]:
    try:
        source = os.path.abspath(get_logs_path(config, files))
        temporary = os.path.abspath(
            resolve_required_path(
                config,
                files,
                "SYSTEM.PATHS.TEMP",
                error_message="Temporary path is not configured.",
            )
        )
    except (StateError, ValueError) as exception:
        raise logs_export_failure(
            "logs_export_paths",
            422,
            "Check the configured logs and temporary directories.",
            exception,
        ) from exception
    if (
        is_same_path(source, temporary)
        or is_path_inside_directory(source, temporary)
        or is_path_within_base(source, temporary)
    ):
        raise SecurityError("Logs export temporary directory must be outside the logs tree.")
    source_root = os.path.splitdrive(source)[0] + os.sep
    temporary_root = os.path.splitdrive(temporary)[0] + os.sep
    try:
        root_identity = FileIdentity.from_stat(stat_managed_path(source_root, source))
    except (FileNotFoundError, FileStorageSecurityError) as exception:
        if isinstance(exception, FileNotFoundError) or isinstance(
            exception.__cause__, FileNotFoundError
        ):
            raise logs_export_failure(
                "logs_export_missing",
                404,
                "The configured logs directory is missing. Check logging settings.",
                exception,
            ) from exception
        raise
    if not root_identity.is_directory:
        raise SecurityError("Configured logs source is not a directory.")
    try:
        temporary_identity = FileIdentity.from_stat(stat_managed_path(temporary_root, temporary))
    except (FileNotFoundError, FileStorageSecurityError) as exception:
        if isinstance(exception, FileNotFoundError) or isinstance(
            exception.__cause__, FileNotFoundError
        ):
            raise logs_export_failure(
                "logs_export_paths",
                422,
                "The configured temporary directory is missing. Check storage settings.",
                exception,
            ) from exception
        raise
    if not temporary_identity.is_directory:
        raise SecurityError("Configured temporary root is not a directory.")
    return source, temporary, source_root, root_identity


def _prepare_logs_export(
    *,
    config: ConfigProviderProtocol,
    files: FilesProviderProtocol,
    storage_manager: StorageManagerProtocol,
    cancellation_event: Event,
    deadline: MonotonicDeadline,
) -> ZipArchiveResult:
    check_cancellation_deadline(cancellation_event, deadline, operation="logs.export")
    try:
        source, temporary, source_root, root_identity = _resolve_logs_export_paths(config, files)
    except ValueError as exception:
        raise logs_export_failure(
            "logs_export_paths",
            422,
            "Check the configured logs and temporary directories.",
            exception,
        ) from exception
    check_cancellation_deadline(cancellation_event, deadline, operation="logs.export")
    started = utc_now()
    capture_started = datetime_to_utc_iso(started)
    download_filename = f"soai-logs_{__version__}_{started.strftime('%Y%m%dT%H%M%S%fZ')}.zip"
    snapshot = create_scoped_temp_directory(temporary, ".tmp.logs-export-")
    result: ZipArchiveResult | None = None
    transferred = False
    try:
        try:
            limits = default_archive_resource_limits()
            budget = ArchivePlanningBudget(limits)
            inventory = inventory_logs(
                source,
                source_root=source_root,
                root_identity=root_identity,
                configured_log_paths=resolve_logs_export_file_paths(config, source),
                budget=budget,
                cancellation_event=cancellation_event,
                deadline=deadline,
            )
            plan = capture_logs(
                inventory,
                source_root=source_root,
                snapshot_path=snapshot,
                storage_manager=storage_manager,
                budget=budget,
                maximum_archive_bytes=limits.max_expanded_bytes,
                cancellation_event=cancellation_event,
                deadline=deadline,
                capture_started=capture_started,
                download_filename=download_filename,
            )
            check_cancellation_deadline(cancellation_event, deadline, operation="logs.export")
            with storage_manager.reserve_disk_space(
                path=temporary,
                required_bytes=plan.required_bytes,
                operation="logs.export.archive",
                details={"required_bytes": plan.required_bytes},
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=plan.required_bytes):
                    result = write_zip_archive(
                        plan=plan,
                        root_path=snapshot,
                        temp_directory=temporary,
                        cancellation_event=cancellation_event,
                        deadline=deadline,
                        operation="logs.export",
                        prefix=".tmp.logs-export-",
                    )
        finally:
            primary_exception = sys.exception()
            try:
                remove_scoped_temp_directory(snapshot)
            except OSError as cleanup_exception:
                if primary_exception is None:
                    raise
                primary_exception.add_note(f"Logs snapshot cleanup failed: {cleanup_exception}")
        check_cancellation_deadline(cancellation_event, deadline, operation="logs.export")
        if result is None:
            raise StateError("Logs export completed without an archive.")
        transferred = True
        return result
    finally:
        if result is not None and not transferred:
            primary_exception = sys.exception()
            try:
                remove_completed_zip_archive(result)
            except OSError as cleanup_exception:
                if primary_exception is None:
                    raise
                primary_exception.add_note(
                    f"Completed logs archive cleanup failed: {cleanup_exception}"
                )
