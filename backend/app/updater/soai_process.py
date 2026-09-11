"""SoAI - SoAI process lifecycle operations for software updates [backend/app/updater/soai_process.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from app.updater.soai_instance import resolve_running_soai_pid, wait_for_instance_lock_release
from app.updater.software_update_task_logging import log_software_update_task_for_dependencies
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.system.commands import run_argv_capture
from core.system.process_launcher import DEVNULL_STREAM, spawn_handoff_process
from core.system.subprocess_platform import windows_isolated_process_creationflags
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from app.updater.dependencies import SoftwareUpdateServiceDependencies
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "InstanceStopResult",
    "stop_running_instance",
    "is_pid_running",
    "start_soai",
    "stop_soai",
    "wait_for_instance_shutdown",
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


def wait_for_instance_shutdown(
    *,
    logger: LoggerProtocol,
    platform_name: str,
    pid: int,
    base_path: str,
    allow_force: bool = True,
) -> bool:
    logger.info("Waiting for SoAI process (PID: %s) to shut down gracefully...", pid)
    for _ in range(60):
        if not is_pid_running(platform_name=platform_name, pid=pid):
            logger.info("SoAI process has terminated.")
            sleep_seconds(STANDARD_DELAY_SEC)
            break
        sleep_seconds(STANDARD_DELAY_SEC)
    else:
        if not allow_force:
            logger.error(
                "Acknowledged updater did not observe application shutdown; update aborted."
            )
            return False
        logger.warning(
            "SoAI process (PID: %s) did not shut down in time. Attempting forceful termination.",
            pid,
        )
        if not stop_soai(logger=logger, platform_name=platform_name, soai_pid=pid):
            return False
    if not wait_for_instance_lock_release(logger=logger, base_path=base_path):
        logger.error("SoAI instance lock remains held after handoff shutdown. Update aborted.")
        return False
    return True


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
    config_path: str,
) -> ManagedProcess | None:
    if not main_py_path:
        logger.warning("Main application path is not initialized.")
        return None
    if not os.path.exists(main_py_path):
        logger.warning("'main.py' not found at %s. Cannot restart SoAI.", main_py_path)
        return None
    logger.info("Restarting SoAI from %s...", main_py_path)
    environment = dict(os.environ)
    environment["SOAI_CONFIG_PATH"] = config_path
    try:
        if platform_name == "Windows":
            process_handle = spawn_handoff_process(
                [get_venv_python_executable(get_venv_path(base_path)), main_py_path],
                cwd=base_path,
                env=environment,
                creationflags=windows_isolated_process_creationflags(),
                stdin=DEVNULL_STREAM,
                stdout=DEVNULL_STREAM,
                stderr=DEVNULL_STREAM,
            )
        else:
            process_handle = spawn_handoff_process(
                [get_venv_python_executable(get_venv_path(base_path)), main_py_path],
                cwd=base_path,
                env=environment,
                start_new_session=True,
            )
        logger.info("SoAI restart command issued.")
        return process_handle
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to restart SoAI.",
            operation=OPERATION_APPLICATION_UPDATER_START_SOAI,
            level="error",
        )
    return None


@dataclass(frozen=True, slots=True)
class InstanceStopResult:
    can_continue: bool
    should_restart: bool
    cancelled: bool = False


def stop_running_instance(
    deps: SoftwareUpdateServiceDependencies,
    *,
    task_id: str,
    latest_version: str,
) -> InstanceStopResult:
    should_restart = True
    if deps.args.wait_for_pid is not None:
        stopped = wait_for_instance_shutdown(
            logger=deps.logger,
            platform_name=deps.platform_name,
            pid=deps.args.wait_for_pid,
            base_path=deps.base_path,
            allow_force=deps.args.task_id is None,
        )
        return InstanceStopResult(can_continue=stopped, should_restart=stopped)
    is_running, running_pid = resolve_running_soai_pid(
        logger=deps.logger,
        base_path=deps.base_path,
        temp_path=deps.temp_path,
        platform_name=deps.platform_name,
        expected_edition=deps.updater.edition,
    )
    if not is_running:
        return InstanceStopResult(can_continue=True, should_restart=False)
    if running_pid is None:
        deps.logger.error(
            "SoAI appears to be running (instance lock is held), but updater could not determine its PID. Please stop SoAI manually and run updater again.",
        )
        return InstanceStopResult(can_continue=False, should_restart=should_restart)
    deps.logger.info("SoAI is running with PID: %s", running_pid)
    if (not deps.args.silent) and input(
        "SoAI must be stopped to continue. Stop it now? (y/n): ",
    ).lower().strip() != "y":
        deps.logger.info("Update cancelled by user.")
        return InstanceStopResult(
            can_continue=False,
            should_restart=should_restart,
            cancelled=True,
        )
    log_software_update_task_for_dependencies(
        deps,
        task_id=task_id,
        to_version=latest_version,
        status="started",
        message=f"Updating from v{deps.local_version} to v{latest_version}",
    )
    if not stop_soai(
        logger=deps.logger,
        platform_name=deps.platform_name,
        soai_pid=running_pid,
    ):
        deps.logger.warning(
            "Failed to stop SoAI. Please stop it manually and run the updater again.",
        )
        return InstanceStopResult(can_continue=False, should_restart=should_restart)
    if not wait_for_instance_lock_release(
        logger=deps.logger,
        base_path=deps.base_path,
        timeout_sec=30.0,
    ):
        deps.logger.warning(
            "SoAI instance lock did not release after shutdown. Aborting update for safety.",
        )
        return InstanceStopResult(can_continue=False, should_restart=should_restart)
    return InstanceStopResult(can_continue=True, should_restart=should_restart)
