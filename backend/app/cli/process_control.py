"""SoAI - CLI process control helpers (subprocess spawning, signal handling) [backend/app/cli/process_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import NoReturn

import psutil

from app.cli.windows_console_service import (
    WindowsConsoleService,
    WindowsConsoleServiceDependencies,
)
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.environment_flags import is_soai_gui_launched

__all__ = (
    "finalize_and_force_exit",
    "force_exit_after_timeout",
    "setup_signal_handlers",
)

OPERATION_APP_CLI_PROCESS_CONTROL_FORCE_EXIT_AFTER_TIMEOUT = (
    "app.cli.process_control.force_exit_after_timeout"
)
OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_FLUSH_STDERR = "main.finalize_and_force_exit.flush_stderr"
OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_FLUSH_STDOUT = "main.finalize_and_force_exit.flush_stdout"
OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_LOGGING_SHUTDOWN = (
    "main.finalize_and_force_exit.logging_shutdown"
)


def finalize_and_force_exit(exit_code: int, *, logger: logging.Logger) -> NoReturn:
    try:
        try:
            sys.stdout.flush()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to flush stdout during forced exit (non-critical).",
                operation=OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_FLUSH_STDOUT,
                level="debug",
            )
        try:
            sys.stderr.flush()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to flush stderr during forced exit (non-critical).",
                operation=OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_FLUSH_STDERR,
                level="debug",
            )
        try:
            logging.shutdown()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to shutdown logging during forced exit (non-critical).",
                operation=OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_LOGGING_SHUTDOWN,
                level="debug",
            )
    finally:
        os._exit(int(exit_code))


def setup_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
    *,
    logger: logging.Logger,
    restart_signal_event: threading.Event,
) -> WindowsConsoleService | None:
    def _handle_stop() -> None:
        logger.info("Signal received, setting stop event for graceful shutdown.")
        if not loop.is_closed():
            loop.call_soon_threadsafe(stop_event.set)

    def _handle_restart() -> None:
        logger.info("Restart signal received (SIGUSR1). Initiating graceful restart.")
        restart_signal_event.set()
        if not loop.is_closed():
            loop.call_soon_threadsafe(stop_event.set)

    if os.name == "nt":
        logger.info("Setting up Windows-native console control handler for graceful shutdown.")
        console_service = WindowsConsoleService(
            WindowsConsoleServiceDependencies(logger=logger),
        )
        if is_soai_gui_launched():
            console_service.ignore_gui_control_signals()
        else:
            console_service.register_ctrl_handler(_handle_stop)
        signal.signal(signal.SIGTERM, lambda _signum, _frame: _handle_stop())
        logger.info("Windows process control handlers registered.")
        return console_service

    logger.info("Setting up Unix signal handlers for graceful shutdown.")
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop)
    loop.add_signal_handler(signal.SIGUSR1, _handle_restart)
    return None


def force_exit_after_timeout(pid: int, timeout: int, logger: logging.Logger) -> None:
    logger.critical(
        "Shutdown has been hanging for over %.3fs. Forcing process termination (PID: %s).",
        timeout,
        pid,
    )
    try:
        process = psutil.Process(pid)
        process.kill()
    except psutil.NoSuchProcess:
        logger.info("Shutdown watchdog fired, but process had already terminated.")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Shutdown watchdog failed to terminate process.",
            operation=OPERATION_APP_CLI_PROCESS_CONTROL_FORCE_EXIT_AFTER_TIMEOUT,
            details={"pid": pid},
            level="critical",
        )
