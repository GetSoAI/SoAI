"""SoAI - SoAI process lifecycle operations for software updates [backend/app/updater/soai_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

import psutil

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.system.commands import run_argv_capture
from core.system.process_launcher import DEVNULL_STREAM, spawn_background_process
from core.system.subprocess_platform import windows_isolated_process_creationflags
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.sleep import sleep_seconds

__all__ = (
    "is_pid_running",
    "start_soai",
    "stop_soai",
    "wait_for_pid_exit",
)

OPERATION_APPLICATION_UPDATER_FORCE_KILL_SOAI = "application_updater.force_kill_soai"
OPERATION_APPLICATION_UPDATER_FORCE_KILL_SOAI_PSUTIL = "application_updater.force_kill_soai.psutil"
OPERATION_APPLICATION_UPDATER_START_SOAI = "application_updater.start_soai"
OPERATION_APPLICATION_UPDATER_STOP_SOAI = "application_updater.stop_soai"
OPERATION_APPLICATION_UPDATER_TERMINATE_SOAI_PSUTIL = "application_updater.terminate_soai.psutil"


def is_pid_running(*, platform_name: str, pid: int) -> bool:
    try:
        if platform_name == "Windows":
            result = run_argv_capture(["tasklist", "/FI", f"PID eq {pid}"], timeout=5)
            return result.return_code == 0 and str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def wait_for_pid_exit(
    *,
    logger: LoggerProtocol,
    platform_name: str,
    pid: int,
) -> bool:
    logger.info("Waiting for SoAI process (PID: %s) to shut down gracefully...", pid)
    for _ in range(60):
        if not is_pid_running(platform_name=platform_name, pid=pid):
            logger.info("SoAI process has terminated.")
            sleep_seconds(STANDARD_DELAY_SEC)
            return True
        sleep_seconds(STANDARD_DELAY_SEC)
    logger.warning(
        "SoAI process (PID: %s) did not shut down in time. Attempting forceful termination.",
        pid,
    )
    return stop_soai(
        logger=logger,
        platform_name=platform_name,
        soai_pid=pid,
    )


def stop_soai(
    *,
    logger: LoggerProtocol,
    platform_name: str,
    soai_pid: int | None,
) -> bool:
    if not soai_pid:
        return True
    try:
        logger.info("Sending termination signal to PID %s...", soai_pid)
        try:
            proc = psutil.Process(int(soai_pid))
            proc.terminate()
        except psutil.NoSuchProcess:
            logger.warning("Process with PID %s not found via psutil.", soai_pid)
        except RECOVERABLE_EXCEPTIONS as psutil_error:
            log_exception(
                logger,
                psutil_error,
                message="psutil terminate failed.",
                operation=OPERATION_APPLICATION_UPDATER_TERMINATE_SOAI_PSUTIL,
                level="warning",
            )
        for _ in range(15):
            if not is_pid_running(platform_name=platform_name, pid=soai_pid):
                logger.info("SoAI stopped gracefully.")
                return True
            sleep_seconds(STANDARD_DELAY_SEC)
    except OSError:
        logger.warning(
            "Process with PID %s not found or permission denied for termination.",
            soai_pid,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error sending SIGTERM to process",
            operation=OPERATION_APPLICATION_UPDATER_STOP_SOAI,
            details={"pid": soai_pid},
        )
    try:
        logger.warning("SoAI did not stop gracefully. Force killing process tree...")
        try:
            proc = psutil.Process(int(soai_pid))
            for child in proc.children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    continue
            proc.kill()
        except RECOVERABLE_EXCEPTIONS as psutil_error:
            log_exception(
                logger,
                psutil_error,
                message="psutil force-kill failed.",
                operation=OPERATION_APPLICATION_UPDATER_FORCE_KILL_SOAI_PSUTIL,
                level="warning",
            )
            return False
        sleep_seconds(STANDARD_DELAY_SEC)
        if not is_pid_running(platform_name=platform_name, pid=soai_pid):
            logger.info("SoAI process terminated forcefully.")
            return True
        logger.warning("Failed to terminate process forcefully.")
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Error force-killing SoAI process {soai_pid}.",
            operation=OPERATION_APPLICATION_UPDATER_FORCE_KILL_SOAI,
            level="error",
        )
        return False


def start_soai(
    *,
    logger: LoggerProtocol,
    platform_name: str,
    base_path: str,
    main_py_path: str | None,
) -> None:
    if not main_py_path:
        logger.warning("Main application path is not initialized.")
        return
    if not os.path.exists(main_py_path):
        logger.warning("'main.py' not found at %s. Cannot restart SoAI.", main_py_path)
        return
    logger.info("Restarting SoAI from %s...", main_py_path)
    try:
        if platform_name == "Windows":
            spawn_background_process(
                [sys.executable, main_py_path],
                cwd=base_path,
                creationflags=windows_isolated_process_creationflags(),
                stdin=DEVNULL_STREAM,
                stdout=DEVNULL_STREAM,
                stderr=DEVNULL_STREAM,
            )
        else:
            spawn_background_process(
                [sys.executable, main_py_path],
                cwd=base_path,
                start_new_session=True,
            )
        logger.info("SoAI restart command issued.")
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to restart SoAI.",
            operation=OPERATION_APPLICATION_UPDATER_START_SOAI,
            level="error",
        )
