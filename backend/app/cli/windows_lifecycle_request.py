"""SoAI - Windows CLI lifecycle request writing [backend/app/cli/windows_lifecycle_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from typing import Literal

import psutil

from app.cli.instance_control_pid import resolve_pid_file_path
from app.cli.restart_request import write_lifecycle_request
from app.updater.soai_instance import is_instance_lock_held, resolve_instance_lock_path
from core.bootstrap.config_scalars import read_yaml_scalar_key
from core.bootstrap.launcher_config import detect_config_path
from core.bootstrap.runtime_record_path import DEFAULT_SYSTEM_DATA_PATH
from core.concurrency.deadlines import MonotonicDeadline
from core.config.path_resolution import ConfigPathResolutionError, resolve_path
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.path_coercion import normalize_filesystem_path
from core.platform.os import is_windows
from core.runtime.instance_record import read_verified_runtime_instance_record
from core.runtime.shutdown_marker import resolve_process_shutdown_marker_path
from core.validation.numbers import coerce_float_from_json

__all__ = (
    "write_windows_lifecycle_request",
    "constrain_windows_stop_deadline",
    "complete_instance_stop",
    "verify_stopped_instance",
)

OPERATION_WINDOWS_LIFECYCLE_REQUEST_WRITE = "app.cli.windows_lifecycle_request.write"
WINDOWS_LIFECYCLE_REQUEST_WRITE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    *RECOVERABLE_EXCEPTIONS,
)
WINDOWS_SHUTDOWN_MARKER_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    ConfigPathResolutionError,
    *RECOVERABLE_EXCEPTIONS,
)


def write_windows_lifecycle_request(
    base_dir: str,
    process: psutil.Process,
    action: Literal["restart", "stop"],
    logger: logging.Logger,
) -> str | None:
    pid = process.pid
    try:
        return write_lifecycle_request(base_dir, process, action, logger)
    except psutil.NoSuchProcess:
        logger.info(
            "SoAI process %s exited before %s request could be written.",
            pid,
            action,
        )
        return None
    except psutil.Error as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to write {action} request due to psutil error.",
            operation=OPERATION_WINDOWS_LIFECYCLE_REQUEST_WRITE,
            details={"action": action, "pid": pid},
            level="error",
        )
        return None
    except WINDOWS_LIFECYCLE_REQUEST_WRITE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to write {action} request.",
            operation=OPERATION_WINDOWS_LIFECYCLE_REQUEST_WRITE,
            details={"action": action, "pid": pid},
            level="error",
        )
        return None


def constrain_windows_stop_deadline(
    deadline: MonotonicDeadline, logger: logging.Logger
) -> MonotonicDeadline | None:
    public_deadline = (
        os.getenv("SOAI_WINDOWS_STOP_DEADLINE_SECONDS", None) if is_windows() else None
    )
    if public_deadline is None:
        return deadline
    deadline_seconds = coerce_float_from_json(public_deadline, default=None)
    if deadline_seconds is None:
        logger.error("The Windows public stop deadline is invalid. No stop request was issued.")
        return None
    constrained = MonotonicDeadline(min(deadline.deadline_monotonic, deadline_seconds))
    if constrained.expired():
        logger.warning("The Windows public stop deadline expired. No stop request was issued.")
        return None
    return constrained


def complete_instance_stop(base_dir: str, pid: int, logger: logging.Logger) -> int:
    if is_windows() and not _verify_clean_shutdown_marker(base_dir, logger):
        return 1
    logger.info("SoAI instance (PID %s) has stopped.", pid)
    return 0


def _verify_clean_shutdown_marker(base_dir: str, logger: logging.Logger) -> bool:
    try:
        system_data = resolve_path(
            read_yaml_scalar_key(detect_config_path(base_dir), key="SYSTEM.PATHS.SYSTEM_DATA")
            or DEFAULT_SYSTEM_DATA_PATH,
            base_dir,
        )
        if system_data is None:
            logger.warning(
                "Shutdown recovery storage could not be resolved. Check the system data path."
            )
            return False
        marker = normalize_filesystem_path(resolve_process_shutdown_marker_path(system_data))
        try:
            os.lstat(marker)
        except FileNotFoundError:
            return True
    except WINDOWS_SHUTDOWN_MARKER_EXCEPTIONS as exception:
        logger.warning(
            "Shutdown recovery evidence could not be verified (%s). Check configuration and access permissions before retrying stop.",
            type(exception).__name__,
        )
        return False
    logger.warning(
        "Shutdown ended without verified clean teardown. The recovery marker was retained; inspect the SoAI logs before retrying stop."
    )
    return False


def verify_stopped_instance(
    base_dir: str, logger: logging.Logger, *, expected_edition: str
) -> bool:
    record = read_verified_runtime_instance_record(
        resolve_pid_file_path(base_dir, logger),
        base_dir=base_dir,
        expected_edition=expected_edition,
    )
    if record is not None or is_instance_lock_held(
        logger=logger, lock_path=resolve_instance_lock_path(base_path=base_dir)
    ):
        return False
    return _verify_clean_shutdown_marker(base_dir, logger)
