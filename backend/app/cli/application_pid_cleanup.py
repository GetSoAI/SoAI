"""SoAI - CLI PID lock and file cleanup [backend/app/cli/application_pid_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import psutil

from app.cli.unexpected_shutdown_reporting import (
    coerce_and_log_unexpected_shutdown_exception_and_return_one,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.filesystem.atomic_write_primitives import fsync_directory
from core.runtime.instance_record import (
    canonicalize_runtime_base_dir,
    read_runtime_instance_record,
)

if TYPE_CHECKING:
    from app.application_controller import ApplicationController

__all__ = ("cleanup_pid_files",)

OPERATION_MAIN_SHUTDOWN = "main.shutdown"


def cleanup_pid_files(
    *,
    application_controller: ApplicationController,
    lifecycle_logger: logging.Logger,
    exit_code: int,
) -> int:
    application_context = application_controller.context
    pid_file_path = (
        str(application_context.paths.pid_file_path)
        if application_context.paths.pid_file_path
        else ""
    )
    try:
        if pid_file_path and not _unlink_owned_runtime_record(
            pid_file_path,
            application_context.paths.base_dir,
            lifecycle_logger,
        ):
            exit_code = 1
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        exit_code = coerce_and_log_unexpected_shutdown_exception_and_return_one(
            lifecycle_logger,
            exception,
            message="Unexpected runtime record cleanup failure",
            operation=OPERATION_MAIN_SHUTDOWN,
            level=None,
        )
    return _release_pid_lock(
        application_controller=application_controller,
        lifecycle_logger=lifecycle_logger,
        exit_code=exit_code,
    )


def _release_pid_lock(
    *,
    application_controller: ApplicationController,
    lifecycle_logger: logging.Logger,
    exit_code: int,
) -> int:
    application_context = application_controller.context
    if not application_context.runtime.pid_lock:
        return exit_code
    try:
        application_context.runtime.pid_lock.release()
        return exit_code
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Failed to release PID lock.",
            operation=OPERATION_MAIN_SHUTDOWN,
        )
        return 1
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        return coerce_and_log_unexpected_shutdown_exception_and_return_one(
            lifecycle_logger,
            exception,
            message="Unexpected PID lock release failure.",
            operation=OPERATION_MAIN_SHUTDOWN,
            level="error",
        )


def _unlink_owned_runtime_record(
    path: str,
    base_dir: str,
    lifecycle_logger: logging.Logger,
) -> bool:
    try:
        record = read_runtime_instance_record(path)
    except FileNotFoundError:
        return True
    except (OSError, ValidationError) as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Runtime instance record could not be validated during cleanup",
            operation=OPERATION_MAIN_SHUTDOWN,
        )
        return False
    try:
        process_create_time_ns = int(
            round(psutil.Process(os.getpid()).create_time() * 1_000_000_000),
        )
    except psutil.Error as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Current process identity could not be validated during cleanup",
            operation=OPERATION_MAIN_SHUTDOWN,
        )
        return False
    if (
        record.pid != os.getpid()
        or record.process_create_time_ns != process_create_time_ns
        or record.base_dir != canonicalize_runtime_base_dir(base_dir)
    ):
        lifecycle_logger.error(
            "Runtime instance record ownership changed before cleanup; refusing deletion.",
        )
        return False
    try:
        os.unlink(path)
        fsync_directory(os.path.dirname(path), strict=True)
        return True
    except FileNotFoundError:
        return True
    except OSError as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Failed to remove owned runtime instance record",
            operation=OPERATION_MAIN_SHUTDOWN,
        )
        return False
