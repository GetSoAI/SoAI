"""SoAI - CLI commands for instance control operations [backend/app/cli/instance_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import signal

import psutil

from app.cli.instance_control_pid import read_running_pid
from app.cli.instance_control_waits import (
    read_runtime_id,
    wait_for_api_health_up,
    wait_for_process_exit,
    wait_for_restart,
    wait_for_stop_api_down,
)
from app.cli.restart_launcher import spawn_replacement_application
from app.cli.status.display import display_enhanced_status
from app.cli.windows_lifecycle_request import write_windows_lifecycle_request
from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.platform.os import is_windows
from core.timing.constants import EXTENDED_TIMEOUT_SEC

__all__ = (
    "handle_restart",
    "handle_status",
    "handle_stop",
)

OPERATION = "app.cli.instance_control.send_signal"


STOP_TOTAL_TIMEOUT_SECONDS = 120.0
RESTART_TOTAL_TIMEOUT_SECONDS = STOP_TOTAL_TIMEOUT_SECONDS
STOP_FORCE_KILL_TIMEOUT_SECONDS = 10.0


def _send_signal(pid: int, sig: signal.Signals, logger: logging.Logger) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        logger.error("Process %s no longer exists.", pid)
        return False
    except PermissionError:
        logger.error("Insufficient permissions to signal process %s.", pid)
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to send signal to process {pid}.",
            operation=OPERATION,
            details={"pid": pid, "signal": sig.name},
            level="error",
        )
        return False


def _force_kill_process(pid: int, logger: logging.Logger) -> bool:
    try:
        process = psutil.Process(pid)
        process.kill()
        logger.critical(
            "Graceful shutdown timed out for SoAI (PID %s). Forced termination requested; waiting up to %s seconds.",
            pid,
            int(STOP_FORCE_KILL_TIMEOUT_SECONDS),
        )
        return True
    except psutil.NoSuchProcess:
        logger.info("SoAI process %s exited before forced termination was needed.", pid)
        return True
    except (PermissionError, psutil.Error) as exception:
        log_exception(
            logger,
            exception,
            message="Failed to force-kill SoAI after graceful stop timeout.",
            operation=OPERATION,
            details={"pid": pid},
            level="critical",
        )
    return False


def _wait_for_forced_termination(pid: int, logger: logging.Logger) -> bool:
    if not _force_kill_process(pid, logger):
        return False
    if wait_for_process_exit(pid, timeout_seconds=STOP_FORCE_KILL_TIMEOUT_SECONDS):
        return True
    logger.critical(
        "SoAI process %s did not exit within %s seconds of forced termination.",
        pid,
        int(STOP_FORCE_KILL_TIMEOUT_SECONDS),
    )
    return False


def _recover_timed_out_restart(
    base_dir: str,
    pid: int,
    logger: logging.Logger,
    *,
    restart_cli_module: str,
    expected_edition: str,
) -> bool:
    if (
        wait_for_api_health_up(
            base_dir,
            expected_edition=expected_edition,
            timeout_seconds=0.0,
        )
        is not None
    ):
        logger.info("SoAI became healthy while restart recovery was being evaluated.")
        return True
    target_pid = read_running_pid(
        base_dir,
        logger,
        expected_edition=expected_edition,
    )
    if target_pid is None:
        target_pid = pid
    logger.critical(
        "SoAI restart did not complete within %s seconds. Force-terminating PID %s and launching a clean replacement.",
        int(RESTART_TOTAL_TIMEOUT_SECONDS),
        target_pid,
    )
    if not _wait_for_forced_termination(target_pid, logger):
        return False
    try:
        spawn_replacement_application(
            base_dir=base_dir,
            lifecycle_logger=logger,
            cli_module=restart_cli_module,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to launch replacement SoAI process after forced restart recovery.",
            operation=OPERATION,
            details={"pid": target_pid},
            level="critical",
        )
        return False
    discovery_info = wait_for_api_health_up(
        base_dir,
        expected_edition=expected_edition,
        timeout_seconds=EXTENDED_TIMEOUT_SEC,
    )
    if discovery_info is None:
        logger.critical(
            "Replacement SoAI process did not become healthy within %s seconds after forced restart recovery.",
            int(EXTENDED_TIMEOUT_SEC),
        )
        return False
    logger.info(
        "Forced restart recovery confirmed (%s://%s:%s).",
        discovery_info.scheme,
        discovery_info.host,
        discovery_info.port,
    )
    return True


def _complete_restart_wait(
    base_dir: str,
    logger: logging.Logger,
    *,
    pid: int,
    initial_runtime_id: str | None,
    restart_cli_module: str,
    expected_edition: str,
) -> int:
    if wait_for_restart(
        base_dir,
        logger,
        pid=pid,
        timeout_seconds=RESTART_TOTAL_TIMEOUT_SECONDS,
        initial_runtime_id=initial_runtime_id,
        expected_edition=expected_edition,
    ):
        logger.info("SoAI restart confirmed.")
        return 0
    if _recover_timed_out_restart(
        base_dir,
        pid,
        logger,
        restart_cli_module=restart_cli_module,
        expected_edition=expected_edition,
    ):
        return 0
    logger.error("SoAI restart recovery failed.")
    return 1


def handle_restart(
    base_dir: str,
    logger: logging.Logger,
    *,
    restart_cli_module: str,
    expected_edition: str,
) -> int:
    pid = read_running_pid(base_dir, logger, expected_edition=expected_edition)
    if pid is None:
        logger.error("No running SoAI instance found. Cannot restart.")
        return 1
    initial_runtime_id = read_runtime_id(
        base_dir,
        logger,
        expected_edition=expected_edition,
    )
    if is_windows():
        request_path = write_windows_lifecycle_request(base_dir, pid, "restart", logger)
        if request_path is None:
            return 1
        logger.info(
            "Restart request written for SoAI instance (PID %s) at %s. Waiting for restart to complete...",
            pid,
            request_path,
        )
        return _complete_restart_wait(
            base_dir,
            logger,
            pid=pid,
            initial_runtime_id=initial_runtime_id,
            restart_cli_module=restart_cli_module,
            expected_edition=expected_edition,
        )
    if not _send_signal(pid, signal.SIGUSR1, logger):
        return 1
    logger.info(
        "Restart signal sent to SoAI instance (PID %s). Waiting for restart to complete...",
        pid,
    )
    return _complete_restart_wait(
        base_dir,
        logger,
        pid=pid,
        initial_runtime_id=initial_runtime_id,
        restart_cli_module=restart_cli_module,
        expected_edition=expected_edition,
    )


def handle_stop(
    base_dir: str,
    logger: logging.Logger,
    *,
    expected_edition: str,
) -> int:
    pid = read_running_pid(base_dir, logger, expected_edition=expected_edition)
    if pid is None:
        logger.error("No running SoAI instance found. Cannot stop.")
        return 1
    windows = is_windows()
    stop_request_description = "lifecycle stop request" if windows else "SIGTERM"
    if windows:
        request_path = write_windows_lifecycle_request(base_dir, pid, "stop", logger)
        if request_path is None:
            return 1
        logger.info(
            "Stop request written for SoAI instance (PID %s) at %s. Waiting for API shutdown...",
            pid,
            request_path,
        )
    else:
        if not _send_signal(pid, signal.SIGTERM, logger):
            return 1
        logger.info("SIGTERM sent to SoAI (PID %s). Waiting for API shutdown...", pid)
    deadline = deadline_after(STOP_TOTAL_TIMEOUT_SECONDS)
    api_down_timeout = deadline.remaining_seconds()
    if not wait_for_stop_api_down(
        base_dir,
        expected_edition=expected_edition,
        pid=pid,
        timeout_seconds=api_down_timeout,
    ):
        logger.warning(
            "SoAI API did not go down within %s seconds after %s (PID %s).",
            int(STOP_TOTAL_TIMEOUT_SECONDS),
            stop_request_description,
            pid,
        )
        return 0 if _wait_for_forced_termination(pid, logger) else 1
    logger.info("SoAI API is down. Waiting for process shutdown (PID %s)...", pid)
    process_exit_timeout = deadline.remaining_seconds()
    if not wait_for_process_exit(pid, timeout_seconds=process_exit_timeout):
        logger.warning(
            "SoAI instance (PID %s) did not stop within %s seconds.",
            pid,
            int(STOP_TOTAL_TIMEOUT_SECONDS),
        )
        return 0 if _wait_for_forced_termination(pid, logger) else 1
    logger.info("SoAI instance (PID %s) has stopped.", pid)
    return 0


def handle_status(
    base_dir: str,
    logger: logging.Logger,
    *,
    expected_edition: str,
) -> int:
    pid = read_running_pid(base_dir, logger, expected_edition=expected_edition)
    if pid is None:
        logger.error("SoAI is not running; start it to use the status command.")
        return 1
    logger.info("SoAI is running (PID %s).", pid)
    display_enhanced_status(
        base_dir,
        pid,
        logger,
        expected_edition=expected_edition,
    )
    return 0
