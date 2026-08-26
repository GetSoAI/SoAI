"""SoAI - Directory lock helpers for install flows [backend/core/bootstrap/install_locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import time

from core.bootstrap.install_filesystem import rmdir_if_exists, unlink_if_exists
from core.errors.exceptions import SoAITimeoutError
from core.system.pid_liveness import pid_is_running
from core.timing.sleep import sleep_seconds

__all__ = (
    "INSTALL_LOCK_ENV",
    "acquire_lock_dir",
    "lock_dir_has_live_owner",
    "read_lock_pid",
    "release_lock_dir",
    "wait_for_lock_dir_clear",
)

INSTALL_LOCK_ENV = "SOAI_INSTALL_LOCK_HELD_PATH"
LOCK_TIMEOUT_SECONDS = 1200.0
MISSING_PID_STALE_SECONDS = 5.0


def acquire_lock_dir(lock_dir: str) -> str:
    resolved_lock_dir = os.path.abspath(lock_dir)
    parent_dir = os.path.dirname(resolved_lock_dir)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    start = time.monotonic()
    missing_pid_started: float | None = None
    while True:
        try:
            os.mkdir(resolved_lock_dir)
            _write_pid_file(resolved_lock_dir)
            return resolved_lock_dir
        except FileExistsError as exception:
            missing_pid_started = _clear_stale_lock(
                resolved_lock_dir,
                missing_pid_started=missing_pid_started,
            )
            if time.monotonic() - start >= LOCK_TIMEOUT_SECONDS:
                raise SoAITimeoutError(
                    "Timed out waiting for SoAI install lock.",
                    details={"lock_dir": resolved_lock_dir},
                    operation="bootstrap.install.acquire_lock_dir",
                ) from exception
            sleep_seconds(1.0)


def release_lock_dir(lock_dir: str) -> None:
    pid_file = os.path.join(lock_dir, "pid")
    unlink_if_exists(pid_file)
    rmdir_if_exists(lock_dir)


def lock_dir_has_live_owner(lock_dir: str) -> bool:
    if not os.path.isdir(lock_dir):
        return False
    pid = read_lock_pid(lock_dir)
    if pid is None:
        return True
    if pid_is_running(pid):
        return True
    _remove_stale_lock(lock_dir)
    return False


def wait_for_lock_dir_clear(lock_dir: str) -> None:
    start = time.monotonic()
    missing_pid_started: float | None = None
    while os.path.isdir(lock_dir):
        missing_pid_started = _clear_stale_lock(
            lock_dir,
            missing_pid_started=missing_pid_started,
        )
        if not os.path.isdir(lock_dir):
            return
        if time.monotonic() - start >= LOCK_TIMEOUT_SECONDS:
            raise SoAITimeoutError(
                "Timed out waiting for SoAI install lock to clear.",
                details={"lock_dir": lock_dir},
                operation="bootstrap.install.wait_for_lock_dir_clear",
            )
        sleep_seconds(1.0)


def _write_pid_file(lock_dir: str) -> None:
    pid_file = os.path.join(lock_dir, "pid")
    try:
        with open(pid_file, "w", encoding="utf-8", errors="strict") as handle:
            handle.write(f"{os.getpid()}\n")
    except OSError:
        rmdir_if_exists(lock_dir)
        raise


def _clear_stale_lock(lock_dir: str, *, missing_pid_started: float | None) -> float | None:
    pid = read_lock_pid(lock_dir)
    if pid is not None:
        if not pid_is_running(pid):
            _remove_stale_lock(lock_dir)
        return None
    if missing_pid_started is None:
        return time.monotonic()
    if time.monotonic() - missing_pid_started >= MISSING_PID_STALE_SECONDS:
        _remove_stale_lock(lock_dir)
        return None
    return missing_pid_started


def _remove_stale_lock(lock_dir: str) -> None:
    unlink_if_exists(os.path.join(lock_dir, "pid"))
    rmdir_if_exists(lock_dir)


def read_lock_pid(lock_dir: str) -> int | None:
    pid_file = os.path.join(lock_dir, "pid")
    text = ""
    read_succeeded = False
    try:
        with open(pid_file, encoding="utf-8", errors="strict") as handle:
            text = handle.readline().strip()
        read_succeeded = True
    except OSError:
        read_succeeded = False
    if not read_succeeded:
        return None
    if not text.isdigit():
        return None
    return int(text)
