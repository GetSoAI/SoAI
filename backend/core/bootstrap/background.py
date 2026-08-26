"""SoAI - Background launch handler for headless startup [backend/core/bootstrap/background.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import subprocess
import sys
import time

from core.bootstrap.background_probe import (
    DiscoveryProbeResult,
    check_api_health,
    resolve_runtime_endpoint_probe,
)
from core.bootstrap.background_runtime_lock import transfer_launcher_runtime_lock
from core.bootstrap.launch_console import emit
from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.errors.exceptions import SoAIError
from core.logging.trace import get_logger
from core.runtime.instance_record import (
    RuntimeInstanceRecord,
    read_verified_runtime_instance_record,
    runtime_record_process_descends_from,
)
from core.runtime.process_identity import SOAI_BACKEND_MAIN_SUBPATH
from core.system.process_launcher import spawn_managed_process
from core.system.subprocess_platform import (
    WINDOWS_CREATE_NEW_PROCESS_GROUP,
    WINDOWS_CREATE_NO_WINDOW,
)
from core.timing.sleep import sleep_seconds

__all__ = (
    "contains_background_flag",
    "launch_background",
    "venv_path",
    "venv_python",
)

BACKGROUND_FLAG_VARIANTS: frozenset[str] = frozenset(
    {
        "--background",
        "-background",
        "background",
    },
)
READINESS_TIMEOUT_SECONDS: float = 120.0
READINESS_POLL_INTERVAL_SECONDS: float = 2.0
SUPERSESSION_READINESS_TIMEOUT_SECONDS: float = 15.0
NO_BROWSER_FLAGS: frozenset[str] = frozenset({"--start-no-browser", "-start-no-browser"})
LOGGER_NAME = "SoAI.core.bootstrap.background"


def venv_path(repo_root_path: str) -> str:
    return get_venv_path(repo_root_path)


def venv_python(venv_path_value: str) -> str:
    return get_venv_python_executable(venv_path_value)


def contains_background_flag(argv: list[str]) -> bool:
    for arg in argv:
        if arg in BACKGROUND_FLAG_VARIANTS:
            return True
    return False


def _strip_background_flag(argv: list[str]) -> list[str]:
    return [arg for arg in argv if arg not in BACKGROUND_FLAG_VARIANTS]


def _ensure_no_browser_flag(argv: list[str]) -> list[str]:
    for arg in argv:
        if arg in NO_BROWSER_FLAGS:
            return argv
    return [*argv, "--start-no-browser"]


def _build_child_command(repo_root_path: str, entrypoint_path: str) -> list[str]:
    venv_path_value = venv_path(repo_root_path)
    python_executable = venv_python(venv_path_value)
    filtered_args = _strip_background_flag(sys.argv[1:])
    filtered_args = _ensure_no_browser_flag(filtered_args)
    return [python_executable, entrypoint_path, *filtered_args]


def _read_installation_record(
    repo_root_path: str,
    *,
    expected_edition: str,
    expected_pid: int | None = None,
) -> RuntimeInstanceRecord | None:
    logger = get_logger(LOGGER_NAME)
    try:
        runtime_record = read_verified_runtime_instance_record(
            resolve_runtime_record_path(repo_root_path, logger=logger),
            base_dir=repo_root_path,
            expected_edition=expected_edition,
            expected_pid=expected_pid,
        )
    except (OSError, SoAIError) as exception:
        logger.debug(
            "Installation runtime record is not currently usable: %s",
            type(exception).__name__,
        )
        runtime_record = None
    return runtime_record


def _read_bootstrap_runtime_record(
    repo_root_path: str,
    *,
    expected_edition: str,
    bootstrap_pid: int,
) -> RuntimeInstanceRecord | None:
    expected_pid = None if os.name == "nt" else bootstrap_pid
    runtime_record = _read_installation_record(
        repo_root_path,
        expected_edition=expected_edition,
        expected_pid=expected_pid,
    )
    if runtime_record is None or runtime_record.api_endpoint is None:
        return None
    if runtime_record.pid == bootstrap_pid:
        return runtime_record
    if os.name != "nt":
        return None
    return (
        runtime_record
        if runtime_record_process_descends_from(runtime_record, bootstrap_pid)
        else None
    )


def _format_ready_message(
    discovery: DiscoveryProbeResult,
    child_pid: int,
) -> str:
    return (
        "SoAI is fully running in the background at "
        f"{discovery.scheme}://{discovery.host}:{discovery.port} (PID {child_pid})."
    )


def _spawn_detached_child(
    command: list[str],
) -> subprocess.Popen[str] | subprocess.Popen[bytes]:
    if os.name == "nt":
        creation_flags = WINDOWS_CREATE_NEW_PROCESS_GROUP | WINDOWS_CREATE_NO_WINDOW
        return spawn_managed_process(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
            close_fds=True,
        )
    return spawn_managed_process(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _poll_until_ready(
    child_process: subprocess.Popen[str] | subprocess.Popen[bytes],
    repo_root_path: str,
    timeout_seconds: float,
    *,
    expected_edition: str,
    prior_runtime_id: str | None = None,
) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds
    supersession_deadline: float | None = None
    while time.monotonic() < deadline:
        exit_code = child_process.poll()
        if exit_code is not None:
            if supersession_deadline is None:
                supersession_deadline = min(
                    deadline,
                    time.monotonic() + SUPERSESSION_READINESS_TIMEOUT_SECONDS,
                )
            replacement_record = _read_installation_record(
                repo_root_path,
                expected_edition=expected_edition,
            )
            if (
                replacement_record is not None
                and replacement_record.pid != child_process.pid
                and replacement_record.runtime_id != prior_runtime_id
            ):
                if replacement_record.api_endpoint is not None:
                    replacement_probe = resolve_runtime_endpoint_probe(
                        replacement_record.api_endpoint
                    )
                    if check_api_health(replacement_probe):
                        return (
                            True,
                            _format_ready_message(
                                replacement_probe,
                                replacement_record.pid,
                            ),
                        )
            if exit_code != 0:
                return (
                    False,
                    f"Background process exited prematurely with code {exit_code}.",
                )
            if time.monotonic() < supersession_deadline:
                sleep_seconds(READINESS_POLL_INTERVAL_SECONDS)
                continue
            return (False, "Background process exited before readiness.")
        child_record = _read_bootstrap_runtime_record(
            repo_root_path,
            expected_edition=expected_edition,
            bootstrap_pid=child_process.pid,
        )
        if child_record is not None and child_record.api_endpoint is not None:
            child_probe = resolve_runtime_endpoint_probe(child_record.api_endpoint)
            if check_api_health(child_probe):
                return (True, _format_ready_message(child_probe, child_record.pid))
        sleep_seconds(READINESS_POLL_INTERVAL_SECONDS)
    return (
        False,
        f"Timed out after {timeout_seconds:.0f}s waiting for SoAI to become ready.",
    )


def _terminate_child_after_lock_transfer_failure(
    child_process: subprocess.Popen[str] | subprocess.Popen[bytes],
) -> None:
    child_process.terminate()
    try:
        child_process.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        child_process.kill()
        try:
            child_process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            emit(
                "ERROR",
                f"Failed to stop background process after lock transfer failure: PID {child_process.pid}",
            )


def launch_background(
    repo_root_path: str,
    *,
    expected_edition: str,
    entrypoint_path: str | None = None,
) -> int:
    exit_code = 1
    prior_runtime_record = _read_installation_record(
        repo_root_path,
        expected_edition=expected_edition,
    )
    prior_runtime_id = prior_runtime_record.runtime_id if prior_runtime_record is not None else None
    resolved_entrypoint_path = entrypoint_path or os.path.join(
        repo_root_path,
        SOAI_BACKEND_MAIN_SUBPATH,
    )
    command = _build_child_command(repo_root_path, resolved_entrypoint_path)
    python_executable = command[0]
    if not os.path.isfile(python_executable):
        emit(
            "ERROR",
            f"Virtual environment python not found at '{python_executable}'. Run bootstrap first.",
        )
        return 1
    try:
        child_process = _spawn_detached_child(command)
    except (OSError, ValueError) as spawn_error:
        emit(
            "ERROR",
            f"Failed to spawn background process: {type(spawn_error).__name__}: {spawn_error}",
        )
        exit_code = 1
    else:
        if not transfer_launcher_runtime_lock(child_process.pid):
            _terminate_child_after_lock_transfer_failure(child_process)
            return 1
        emit(
            "INFO",
            f"Background process spawned (PID {child_process.pid}). Waiting for readiness...",
        )
        try:
            success, message = _poll_until_ready(
                child_process,
                repo_root_path,
                READINESS_TIMEOUT_SECONDS,
                expected_edition=expected_edition,
                prior_runtime_id=prior_runtime_id,
            )
        except KeyboardInterrupt:
            emit("WARN", "Interrupted. SoAI may still be starting in the background.")
            exit_code = 130
        else:
            if success:
                emit("INFO", message)
                exit_code = 0
            else:
                emit("ERROR", message)
                exit_code = 1
    return exit_code
