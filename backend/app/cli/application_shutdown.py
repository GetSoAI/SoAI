"""SoAI - CLI final application shutdown sequence [backend/app/cli/application_shutdown.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import math
import os
import threading
from typing import TYPE_CHECKING

from app.cli.application_pid_cleanup import cleanup_pid_files
from app.cli.process_control import force_exit_after_timeout
from app.cli.restart_launcher import relaunch_application
from app.cli.unexpected_shutdown_reporting import (
    coerce_and_log_unexpected_shutdown_exception_and_return_one,
)
from app.lifecycle.budgets import resolve_lifecycle_shutdown_budgets
from app.lifecycle.process_cleanup import cleanup_lingering_processes
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from app.application_controller import ApplicationController
    from core.system.protocols import ManagedProcessProtocol

__all__ = ("shutdown_application",)

OPERATION_MAIN_SHUTDOWN = "main.shutdown"


async def shutdown_application(
    *,
    application_controller: ApplicationController,
    base_dir: str,
    lifecycle_logger: logging.Logger,
    restart_cli_module: str,
    exit_code: int,
) -> int:
    lifecycle_logger.info("Initiating final shutdown sequence.")
    application_context = application_controller.context
    pid = os.getpid()
    shutdown_budgets = resolve_lifecycle_shutdown_budgets(
        application_context.services.configuration.config,
    )
    shutdown_timeout_int = math.ceil(shutdown_budgets.watchdog_timeout_sec)
    shutdown_watchdog = threading.Timer(
        shutdown_timeout_int,
        force_exit_after_timeout,
        args=[pid, shutdown_timeout_int, lifecycle_logger],
    )
    watchdog_started = False
    try:
        shutdown_watchdog.start()
        watchdog_started = True
        lifecycle_logger.debug(
            "Shutdown initiated. A %.3fs watchdog has been armed to prevent hangs.",
            shutdown_timeout_int,
        )
        exit_code = await _run_controller_shutdown(
            application_controller=application_controller,
            lifecycle_logger=lifecycle_logger,
            exit_code=exit_code,
        )
        exit_code = _cleanup_lingering_children(
            pid=pid,
            base_dir=base_dir,
            lifecycle_logger=lifecycle_logger,
            timeout_sec=shutdown_budgets.force_cleanup_timeout_sec,
            exit_code=exit_code,
            transferred_processes=application_context.runtime.transferred_processes,
        )
        exit_code = cleanup_pid_files(
            application_controller=application_controller,
            lifecycle_logger=lifecycle_logger,
            exit_code=exit_code,
        )
    finally:
        shutdown_watchdog.cancel()
        if watchdog_started:
            shutdown_watchdog.join()
    if application_context.runtime.restart_requested:
        lifecycle_logger.debug(
            "Graceful shutdown complete. Re-executing the application process for restart.",
        )
        relaunch_application(
            base_dir=base_dir,
            lifecycle_logger=lifecycle_logger,
            cli_module=restart_cli_module,
        )
    if application_context.runtime.exit_code != 0:
        exit_code = application_context.runtime.exit_code
    return exit_code


async def _run_controller_shutdown(
    *,
    application_controller: ApplicationController,
    lifecycle_logger: logging.Logger,
    exit_code: int,
) -> int:
    try:
        await application_controller.shutdown()
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Application shutdown sequence failed.",
            operation=OPERATION_MAIN_SHUTDOWN,
            level="critical",
        )
        return 1
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        return coerce_and_log_unexpected_shutdown_exception_and_return_one(
            lifecycle_logger,
            exception,
            message="Unexpected application shutdown sequence failure.",
            operation=OPERATION_MAIN_SHUTDOWN,
            level="critical",
        )
    return exit_code


def _cleanup_lingering_children(
    *,
    pid: int,
    base_dir: str,
    lifecycle_logger: logging.Logger,
    timeout_sec: float,
    exit_code: int,
    transferred_processes: tuple[ManagedProcessProtocol, ...],
) -> int:
    try:
        lifecycle_logger.debug(
            "Graceful shutdown completed within the time limit. Watchdog disarmed.",
        )
        cleanup_ok = cleanup_lingering_processes(
            pid=pid,
            base_dir=base_dir,
            logger=lifecycle_logger,
            timeout_sec=timeout_sec,
            transferred_processes=transferred_processes,
        )
        return exit_code if cleanup_ok else 1
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            lifecycle_logger,
            exception,
            message="Failed to perform final process cleanup.",
            operation=OPERATION_MAIN_SHUTDOWN,
            level="error",
        )
        return 1
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        return coerce_and_log_unexpected_shutdown_exception_and_return_one(
            lifecycle_logger,
            exception,
            message="Unexpected final process cleanup failure.",
            operation=OPERATION_MAIN_SHUTDOWN,
            level="error",
        )
