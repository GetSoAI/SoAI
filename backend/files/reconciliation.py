"""SoAI - File storage reconciliation helpers [backend/files/reconciliation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from core.collections.sets import compute_set_deltas
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.files.operations import async_remove
from core.files.protocols import DatabaseFilesProtocol
from core.filesystem.async_queries import async_isdir
from core.logging.trace import get_logger
from core.timing.constants import RESPONSIVE_TIMEOUT_SEC

__all__ = (
    "PhysicalFileScanResult",
    "collect_physical_files",
    "reconcile_file_storage",
)

LOGGER_NAME = "SoAI.files.reconciliation"
OPERATION = "file_manager.initialize"


@dataclass(frozen=True, slots=True)
class PhysicalFileScanResult:
    paths: set[str]
    scan_error_count: int
    timed_out: bool

    @property
    def scan_had_errors(self) -> bool:
        return self.scan_error_count > 0


def _compute_worker_count(requested_concurrency: int) -> int:
    available_cpus = os.cpu_count() or 4
    return min(requested_concurrency, available_cpus * 2, 32)


async def collect_physical_files(
    storage_root: str,
    concurrency: int,
    timeout_seconds: float,
) -> PhysicalFileScanResult:
    if not await async_isdir(storage_root):
        return PhysicalFileScanResult(paths=set(), scan_error_count=0, timed_out=False)
    normalized_concurrency = max(1, int(concurrency))
    worker_count = _compute_worker_count(normalized_concurrency)
    queue_capacity = max(256, min(worker_count * 512, 16384))
    dir_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_capacity)
    await asyncio.wait_for(dir_queue.put(storage_root), timeout=RESPONSIVE_TIMEOUT_SEC)

    worker_file_sets: list[set[str]] = [set() for _ in range(worker_count)]
    worker_error_counts: list[int] = [0] * worker_count

    def _scan_directory(path: str) -> tuple[list[tuple[str, bool, bool]], int]:
        records: list[tuple[str, bool, bool]] = []
        error_count = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError:
                        error_count += 1
                        continue
                    records.append((entry.path, is_dir, is_file))
        except OSError:
            return ([], 1)
        return (records, error_count)

    async def _worker(worker_index: int) -> None:
        local_files = worker_file_sets[worker_index]
        while True:
            try:
                directory = await dir_queue.get()
            except asyncio.CancelledError:
                return
            try:
                stack = [directory]
                while stack:
                    current_dir = stack.pop()
                    entries, errors = await asyncio.to_thread(_scan_directory, current_dir)
                    if errors:
                        worker_error_counts[worker_index] += errors
                    for entry_path, is_dir, is_file in entries:
                        if is_file:
                            local_files.add(entry_path)
                        elif is_dir:
                            try:
                                dir_queue.put_nowait(entry_path)
                            except asyncio.QueueFull:
                                stack.append(entry_path)
            finally:
                dir_queue.task_done()

    workers = [create_ephemeral_task(_worker(index)) for index in range(worker_count)]
    scan_timed_out = False
    try:
        await asyncio.wait_for(dir_queue.join(), timeout=timeout_seconds)
    except TimeoutError:
        scan_timed_out = True
    finally:
        await cancel_and_await(workers, timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC)
    merged_paths: set[str] = set()
    for file_set in worker_file_sets:
        merged_paths.update(file_set)
    total_scan_errors = sum(worker_error_counts)
    return PhysicalFileScanResult(
        paths=merged_paths,
        scan_error_count=total_scan_errors,
        timed_out=scan_timed_out,
    )


async def reconcile_file_storage(
    database_files: DatabaseFilesProtocol,
    storage_root: str,
    concurrency: int,
    directory_scan_timeout_seconds: float,
) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.debug("Starting file storage reconciliation...")
    try:
        db_filepaths: set[str] = set()
        db_filepath_to_id: dict[str, str] = {}
        for record in await database_files.get_all_file_records_for_reconciliation():
            file_path = record["file_path"]
            if file_path:
                db_filepaths.add(file_path)
                db_filepath_to_id[file_path] = record["id"]
        scan_result = await collect_physical_files(
            storage_root,
            concurrency,
            directory_scan_timeout_seconds,
        )
        if scan_result.timed_out:
            logger.warning(
                "File storage scan timed out after %.0f seconds. Reconciliation will be skipped to avoid acting on incomplete data.",
                directory_scan_timeout_seconds,
            )
            return
        physical_files = scan_result.paths
        ghost_paths, orphaned_files = compute_set_deltas(db_filepaths, physical_files)
        skip_ghost_purge = scan_result.scan_had_errors
        if skip_ghost_purge:
            logger.warning(
                "File storage scan completed with %s error(s). Ghost record purge will be skipped to avoid deleting records based on an incomplete scan.",
                scan_result.scan_error_count,
            )
        if orphaned_files:
            logger.warning(
                "Found %s orphaned file(s) in storage. Purging...",
                len(orphaned_files),
            )
            for fpath in orphaned_files:
                try:
                    await async_remove(fpath)
                    logger.info("Deleted orphaned file: %s", fpath)
                except OSError as exception:
                    log_exception(
                        logger,
                        exception,
                        message="Failed to delete orphaned file",
                        operation=OPERATION,
                        details={"file_path": fpath},
                    )
        if ghost_paths:
            if skip_ghost_purge:
                logger.warning(
                    "Skipping purge of %s potential ghost record(s) due to scan errors.",
                    len(ghost_paths),
                )
            else:
                ghost_record_ids = [db_filepath_to_id[fpath] for fpath in ghost_paths]
                logger.warning(
                    "Found %s ghost record(s) in database. Purging...",
                    len(ghost_record_ids),
                )
                deleted_count = await database_files.delete_files_by_ids(ghost_record_ids)
                logger.info(
                    "Deleted %s ghost record(s) from the database.",
                    deleted_count,
                )
        logger.debug("File storage reconciliation complete.")
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="file_manager.initialize",
        )
        log_exception(
            logger,
            coerced,
            message="Critical error during file storage reconciliation; aborting startup.",
            operation=OPERATION,
            level="critical",
        )
        raise coerced from exception
