"""SoAI - Instance lock and PID discovery for update coordination [backend/app/updater/soai_instance.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

import psutil
from filelock import FileLock, Timeout

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.meta.paths import join_data_abs
from core.runtime.instance_record import read_verified_runtime_instance_record
from core.runtime.process_identity import is_soai_process_command
from core.timing.constants import MODERATE_DELAY_SEC
from core.timing.sleep import sleep_seconds

__all__ = (
    "find_pid_from_instance_lock",
    "find_soai_pid",
    "is_instance_lock_held",
    "resolve_instance_lock_path",
    "resolve_running_soai_pid",
    "wait_for_instance_lock_release",
)

OPERATION_APPLICATION_UPDATER_INSTANCE_LOCK_PREPARE_DIR = (
    "application_updater.instance_lock.prepare_dir"
)
OPERATION_APPLICATION_UPDATER_INSTANCE_LOCK_PROBE = "application_updater.instance_lock.probe"
OPERATION_APPLICATION_UPDATER_INSTANCE_LOCK_PROBE_RELEASE = (
    "application_updater.instance_lock.probe.release"
)


def resolve_instance_lock_path(*, base_path: str) -> str:
    return join_data_abs(base_path, "locks", "soai.instance.lock")


def is_instance_lock_held(*, logger: LoggerProtocol, lock_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to prepare locks directory for instance coordination.",
            operation=OPERATION_APPLICATION_UPDATER_INSTANCE_LOCK_PREPARE_DIR,
            details={"path": lock_path},
            level="warning",
        )
        return True

    try:
        lock = FileLock(lock_path, timeout=0)
        try:
            lock.acquire()
        except Timeout:
            return True
        finally:
            try:
                try:
                    is_locked = bool(lock.is_locked)
                except AttributeError:
                    is_locked = False
                if is_locked:
                    lock.release()
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to release instance lock probe handle (non-critical).",
                    operation=OPERATION_APPLICATION_UPDATER_INSTANCE_LOCK_PROBE_RELEASE,
                    details={"path": lock_path},
                    level="debug",
                )
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to probe SoAI instance lock",
            operation=OPERATION_APPLICATION_UPDATER_INSTANCE_LOCK_PROBE,
            details={"path": lock_path},
            level="warning",
        )
        return True


def find_soai_pid(
    *,
    logger: LoggerProtocol,
    platform_name: str,
    temp_path: str,
    base_path: str,
    expected_edition: str,
) -> int | None:
    pid_file = os.path.join(temp_path, "soai.pid")
    _ = platform_name
    try:
        runtime_record = read_verified_runtime_instance_record(
            pid_file,
            base_dir=base_path,
            expected_edition=expected_edition,
        )
    except (OSError, ValidationError) as exception:
        logger.warning(
            "Runtime instance record could not be validated: %s",
            type(exception).__name__,
        )
        return None
    return runtime_record.pid if runtime_record is not None else None


def find_pid_from_instance_lock(
    *,
    base_path: str,
    lock_path: str,
) -> int | None:
    resolved_lock = os.path.abspath(lock_path)
    candidates: list[int] = []

    for proc in psutil.process_iter(attrs=["pid"]):
        pid_value = int(proc.pid)
        if pid_value <= 0:
            continue
        if pid_value == os.getpid():
            continue
        try:
            open_files = proc.open_files()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except psutil.Error:
            continue

        for open_file in open_files:
            file_path = open_file.path
            try:
                if os.path.abspath(str(file_path)) == resolved_lock:
                    candidates.append(pid_value)
                    break
            except (OSError, TypeError):
                continue

    if not candidates:
        resolved_base_path = os.path.abspath(base_path)
        for proc in psutil.process_iter(attrs=["pid", "cmdline", "cwd", "exe", "name"]):
            pid_value = int(proc.pid)
            if pid_value <= 0:
                continue
            if pid_value == os.getpid():
                continue
            try:
                cmdline = proc.cmdline()
            except psutil.Error:
                continue
            cmdline_lower = [str(arg).lower() for arg in cmdline]
            cmdline_joined = " ".join(cmdline_lower)
            if "app.updater.cli" in cmdline_joined:
                continue
            if not is_soai_process_command(cmdline_lower):
                continue
            try:
                cwd_value = proc.cwd()
            except psutil.Error:
                cwd_value = ""
            try:
                exe_value = proc.exe()
            except psutil.Error:
                exe_value = ""
            candidates_haystack = [
                cwd_value,
                exe_value,
            ] + [str(arg) for arg in cmdline]
            if not any(resolved_base_path in str(value) for value in candidates_haystack if value):
                continue
            candidates.append(pid_value)

    if not candidates:
        return None

    unique_candidates = sorted(set(candidates))
    for pid_value in unique_candidates:
        try:
            proc = psutil.Process(pid_value)
            cmdline_lower = [str(arg).lower() for arg in proc.cmdline()]
            cmdline_joined = " ".join(cmdline_lower)
        except psutil.Error:
            continue
        if "app.updater.cli" in cmdline_joined:
            continue
        if is_soai_process_command(cmdline_lower):
            return pid_value
    return unique_candidates[0]


def resolve_running_soai_pid(
    *,
    logger: LoggerProtocol,
    base_path: str,
    temp_path: str,
    platform_name: str,
    expected_edition: str,
) -> tuple[bool, int | None]:
    pid = find_soai_pid(
        logger=logger,
        platform_name=platform_name,
        temp_path=temp_path,
        base_path=base_path,
        expected_edition=expected_edition,
    )
    lock_path = resolve_instance_lock_path(base_path=base_path)
    lock_held = is_instance_lock_held(logger=logger, lock_path=lock_path)
    if pid is not None:
        return (True, pid)
    if not lock_held:
        return (False, None)
    pid_from_lock = find_pid_from_instance_lock(
        base_path=base_path,
        lock_path=lock_path,
    )
    if pid_from_lock is not None:
        return (True, pid_from_lock)
    return (True, None)


def wait_for_instance_lock_release(
    *,
    logger: LoggerProtocol,
    base_path: str,
    timeout_sec: float = 30.0,
) -> bool:
    lock_path = resolve_instance_lock_path(base_path=base_path)
    if timeout_sec <= 0:
        return not is_instance_lock_held(logger=logger, lock_path=lock_path)
    deadline = deadline_after(timeout_sec)
    while not deadline.expired():
        if not is_instance_lock_held(logger=logger, lock_path=lock_path):
            return True
        sleep_seconds(MODERATE_DELAY_SEC)
    return not is_instance_lock_held(logger=logger, lock_path=lock_path)
