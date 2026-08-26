"""SoAI - File lock acquisition and cleanup for instance locking [backend/app/cli/instance_lock/file_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from collections.abc import Iterable

from filelock import FileLock, Timeout

from app.internal_protocols import InstanceLockProtocol
from core.concurrency.deadlines import deadline_after
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.meta.paths import join_data_abs
from core.timing.sleep import sleep_seconds

__all__ = (
    "cleanup_stale_lock_files",
    "resolve_instance_lock_path",
    "try_acquire_instance_lock",
    "wait_for_instance_lock",
)

OPERATION_MAIN_ACQUIRE_INSTANCE_LOCK = "main.acquire_instance_lock"
OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES = "main.cleanup_stale_lock_files"
OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_PROBE = "main.cleanup_stale_lock_files.probe"
OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_RELEASE = "main.cleanup_stale_lock_files.release"
OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_RESOLVE = "main.cleanup_stale_lock_files.resolve"
OPERATION_MAIN_RESOLVE_INSTANCE_LOCK_PATH = "main.resolve_instance_lock_path"


def resolve_instance_lock_path(base_dir: str, *, logger: logging.Logger) -> str | None:
    try:
        resolved_base = os.path.realpath(base_dir)
        return join_data_abs(resolved_base, "locks", "soai.instance.lock")
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to resolve instance lock path",
            operation=OPERATION_MAIN_RESOLVE_INSTANCE_LOCK_PATH,
            details={"base_dir": base_dir},
            level="error",
        )
        return None


def try_acquire_instance_lock(
    lock_file_path: str,
    *,
    logger: logging.Logger,
) -> InstanceLockProtocol | None:
    try:
        lock = FileLock(lock_file_path, timeout=0)
        lock.acquire()
        return lock
    except Timeout:
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to acquire instance lock (non-critical).",
            operation=OPERATION_MAIN_ACQUIRE_INSTANCE_LOCK,
            details={"path": lock_file_path},
            level="debug",
        )
        return None


def wait_for_instance_lock(
    lock_file_path: str,
    *,
    logger: logging.Logger,
    timeout_sec: float,
    poll_interval: float = 0.25,
) -> InstanceLockProtocol | None:
    deadline = deadline_after(timeout_sec)
    while not deadline.expired():
        lock = try_acquire_instance_lock(lock_file_path, logger=logger)
        if lock is not None:
            return lock
        sleep_seconds(poll_interval)
    return None


def cleanup_stale_lock_files(
    base_dir: str,
    *,
    logger: logging.Logger,
    exclude_paths: Iterable[str] | None = None,
) -> None:
    exclude = {os.path.realpath(path) for path in (exclude_paths or [])}
    lock_directories = [
        join_data_abs(base_dir, "locks"),
        base_dir,
        os.path.join(base_dir, "plugins"),
        join_data_abs(base_dir),
        join_data_abs(base_dir, "backups"),
        join_data_abs(base_dir, "temp"),
    ]
    verified_count = 0
    for directory in lock_directories:
        if not os.path.isdir(directory):
            continue
        try:
            for name in os.listdir(directory):
                if not name.endswith(".lock"):
                    continue
                try:
                    entry_path = os.path.join(directory, name)
                    resolved_entry = os.path.realpath(entry_path)
                except OSError as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed while resolving lock file entry (non-critical).",
                        operation=OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_RESOLVE,
                        details={"directory": directory, "name": name},
                        level="debug",
                    )
                    continue
                if resolved_entry in exclude:
                    continue
                try:
                    entry_lock = FileLock(entry_path, timeout=0)
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed while probing lock file (non-critical).",
                        operation=OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_PROBE,
                        details={"path": entry_path},
                        level="debug",
                    )
                    continue
                try:
                    entry_lock.acquire()
                    verified_count += 1
                except Timeout:
                    continue
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed while probing lock file (non-critical).",
                        operation=OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_PROBE,
                        details={"path": entry_path},
                        level="debug",
                    )
                    continue
                try:
                    entry_lock.release()
                except (AttributeError, TypeError, ValueError, OSError) as exception:
                    coerced = coerce_to_soai_error(
                        exception,
                        operation=OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_RELEASE,
                    )
                    log_handled_exception(
                        logger,
                        coerced,
                        message="Failed to release lock during stale lock cleanup (non-critical).",
                        operation=OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES_RELEASE,
                        details={"path": entry_path},
                        level="debug",
                    )
        except OSError as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to scan directory for lock files (non-critical).",
                operation=OPERATION_MAIN_CLEANUP_STALE_LOCK_FILES,
                details={"directory": directory},
                level="debug",
            )
    if verified_count > 0:
        logger.info("Verified %s stale lock file(s) as unheld.", verified_count)
