"""SoAI - Instance lock service (PID file and exclusive lock) [backend/app/cli/instance_lock/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os

from app.cli.instance_lock.file_lock import (
    cleanup_stale_lock_files,
    resolve_instance_lock_path,
    try_acquire_instance_lock,
    wait_for_instance_lock,
)
from app.cli.instance_lock.process_candidates import (
    discover_running_instance_pids,
    find_pids_holding_lock_file,
)
from app.cli.instance_lock.process_tree import (
    force_kill_process_native,
    get_current_process_tree_pids,
    terminate_process_native,
)
from app.internal_protocols import InstanceLockProtocol
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.instance_record import (
    RuntimeInstanceRecord,
    create_runtime_instance_record,
    read_verified_runtime_instance_record,
    write_runtime_instance_record,
)

__all__ = ("setup_pid_file_and_lock",)

OPERATION = "main.pid"


def setup_pid_file_and_lock(
    base_dir: str,
    *,
    edition: str,
    temp_dir: str,
    logger: logging.Logger,
) -> InstanceLockProtocol | None:
    instance_lock_path = resolve_instance_lock_path(base_dir, logger=logger)
    if instance_lock_path is None:
        return None
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to create temp directory for PID file",
            operation=OPERATION,
            details={"temp_path": temp_dir},
            level="error",
        )
        return None
    pid_file_path = os.path.join(temp_dir, "soai.pid")
    current_pid = os.getpid()
    try:
        lock_dir = os.path.dirname(instance_lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to create locks directory",
            operation=OPERATION,
            details={"lock_dir": os.path.dirname(instance_lock_path)},
            level="error",
        )
        return None
    lock = try_acquire_instance_lock(instance_lock_path, logger=logger)
    if lock is None:
        existing_record = _read_existing_record(pid_file_path, base_dir, logger)
        if existing_record is None:
            return None
        if existing_record.edition != edition:
            logger.error(
                "Refusing to replace running %s instance with requested %s edition (PID %s).",
                existing_record.edition,
                edition,
                existing_record.pid,
            )
            return None
        existing_pid = existing_record.pid
        lock_holder_pids = frozenset(find_pids_holding_lock_file(instance_lock_path))
        heuristic_pids = discover_running_instance_pids(
            base_dir,
            logger=logger,
            pid_hint=existing_pid,
            lock_holder_pids=lock_holder_pids,
        )
        raw_candidate_pids = sorted(set(heuristic_pids) | lock_holder_pids)
        protected_pids = get_current_process_tree_pids(logger=logger)
        candidate_pids = [pid for pid in raw_candidate_pids if pid not in protected_pids]
        if candidate_pids:
            logger.warning(
                "Another SoAI instance detected (PID(s): %s). Requesting shutdown...",
                ", ".join(str(pid) for pid in candidate_pids),
            )
            for pid in candidate_pids:
                terminate_process_native(
                    pid,
                    logger=logger,
                    exclude_pids=protected_pids,
                )
            lock = wait_for_instance_lock(instance_lock_path, logger=logger, timeout_sec=15.0)
            if lock is None:
                logger.warning(
                    "Graceful shutdown timed out. Force killing PID(s): %s",
                    ", ".join(str(pid) for pid in candidate_pids),
                )
                for pid in candidate_pids:
                    force_kill_process_native(
                        pid,
                        logger=logger,
                        exclude_pids=protected_pids,
                    )
                lock = wait_for_instance_lock(instance_lock_path, logger=logger, timeout_sec=10.0)
        elif raw_candidate_pids and protected_pids:
            logger.error(
                "Instance lock appears held by the current process tree; refusing to terminate.",
            )
            return None
        if lock is None:
            logger.error(
                "Instance lock is held but could not identify owning process. Refusing to start.",
            )
            return None
    try:
        runtime_record = create_runtime_instance_record(
            pid=current_pid,
            base_dir=base_dir,
            edition=edition,
        )
        write_runtime_instance_record(pid_file_path, runtime_record)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to write PID file. Releasing instance lock.",
            operation=OPERATION,
            details={"pid_file_path": pid_file_path},
            level="error",
        )
        lock.release()
        return None
    cleanup_stale_lock_files(
        base_dir,
        logger=logger,
        exclude_paths=[lock.lock_file] if lock.lock_file else [],
    )
    return lock


def _read_existing_record(
    pid_file_path: str,
    base_dir: str,
    logger: logging.Logger,
) -> RuntimeInstanceRecord | None:
    try:
        record = read_verified_runtime_instance_record(
            pid_file_path,
            base_dir=base_dir,
        )
        if record is None:
            logger.error(
                "Instance lock is held but its runtime process identity is stale.",
            )
        return record
    except FileNotFoundError:
        logger.error("Instance lock is held but its runtime record is missing.")
        return None
    except (OSError, ValidationError) as exception:
        logger.error(
            "Instance lock is held but its runtime record is invalid: %s",
            type(exception).__name__,
        )
        return None
