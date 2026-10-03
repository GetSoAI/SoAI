"""SoAI - CLI process control helpers (subprocess spawning, signal handling) [backend/app/cli/process_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import threading
from typing import TYPE_CHECKING, NoReturn

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.environment_flags import is_soai_gui_launched
from core.runtime.process_exit_deadline import ProcessExitDeadline
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

if TYPE_CHECKING:
    from app.internal_protocols import WindowsConsoleControlProtocol

__all__ = (
    "finalize_and_force_exit",
    "setup_signal_handlers",
)

OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_FLUSH_STDERR = "main.finalize_and_force_exit.flush_stderr"
OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_FLUSH_STDOUT = "main.finalize_and_force_exit.flush_stdout"
OPERATION_MAIN_FINALIZE_AND_FORCE_EXIT_LOGGING_SHUTDOWN = (
    "main.finalize_and_force_exit.logging_shutdown"
)


def finalize_and_force_exit(exit_code: int, *, logger: logging.Logger) -> NoReturn:
    final_exit_code = 1
    try:
        with ProcessExitDeadline() as process_exit_deadline:
            process_exit_deadline.begin_finalization(LOCAL_IO_TIMEOUT_SEC)
            final_exit_code = int(exit_code)
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
        os._exit(final_exit_code)


def setup_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    stop_event: asyncio.Event,
    *,
    logger: logging.Logger,
    restart_signal_event: threading.Event,
    windows_console_control: WindowsConsoleControlProtocol | None,
) -> WindowsConsoleControlProtocol | None:
    def _handle_stop() -> None:
        if not loop.is_closed():
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                if not loop.is_closed():
                    raise

    def _handle_restart() -> None:
        restart_signal_event.set()
        _handle_stop()

    if os.name == "nt":
        if windows_console_control is None:
            raise StateError("Windows console control was not composed for the runtime.")
        logger.info("Setting up Windows-native console control handler for graceful shutdown.")
        if is_soai_gui_launched():
            windows_console_control.ignore_gui_control_signals()
        else:
            windows_console_control.register_ctrl_handler(_handle_stop)
        signal.signal(signal.SIGTERM, lambda _signum, _frame: _handle_stop())
        logger.info("Windows process control handlers registered.")
        return windows_console_control

    logger.info("Setting up Unix signal handlers for graceful shutdown.")
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_stop)
    loop.add_signal_handler(signal.SIGUSR1, _handle_restart)
    return None
