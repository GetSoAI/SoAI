"""SoAI - Software update process lock [backend/app/updater/software_update/update_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from app.updater.soai_process import is_pid_running
from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.atomic_writes import atomic_write_text_content
from core.filesystem.open_files import open_text
from core.logging.protocols import LoggerProtocol
from core.meta.paths import join_data_abs
from core.timing.constants import EXTENDED_TIMEOUT_SEC, MODERATE_DELAY_SEC
from core.timing.epoch import epoch_seconds_float
from core.timing.sleep import sleep_seconds

__all__ = (
    "guarded_software_update_lock",
    "resolve_software_update_lock_dir",
)

OPERATION_LOCK_PREPARE = "application_updater.run_software_update.prepare_lock"
OPERATION_LOCK_STALE_CLEANUP = "application_updater.run_software_update.stale_lock_cleanup"


def resolve_software_update_lock_dir(base_path: str) -> str:
    return join_data_abs(base_path, "locks", "soai.update.lock.d")


def _pid_path(lock_dir: str) -> str:
    return os.path.join(lock_dir, "pid")


def _read_lock_pid(lock_dir: str) -> int | None:
    pid_file = _pid_path(lock_dir)
    if not os.path.isfile(pid_file):
        return None
    try:
        with open_text(pid_file, encoding="utf-8", errors="replace") as file_handle:
            raw_value = file_handle.read().strip()
    except OSError:
        return None
    if not raw_value.isdigit():
        return None
    pid_value = int(raw_value)
    if pid_value <= 0:
        return None
    return pid_value


def _lock_without_pid_is_stale(lock_dir: str) -> bool:
    try:
        lock_age_seconds = epoch_seconds_float() - os.path.getmtime(lock_dir)
    except OSError:
        return False
    return lock_age_seconds > EXTENDED_TIMEOUT_SEC


def _remove_stale_lock(lock_dir: str, logger: LoggerProtocol) -> None:
    try:
        pid_file = _pid_path(lock_dir)
        if os.path.exists(pid_file):
            os.remove(pid_file)
        os.rmdir(lock_dir)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to remove stale software update lock.",
            operation=OPERATION_LOCK_STALE_CLEANUP,
            details={"lock_dir": lock_dir},
            level="warning",
        )
        raise


def _write_lock_pid(lock_dir: str) -> None:
    atomic_write_text_content(
        _pid_path(lock_dir),
        f"{os.getpid()}\n",
        ensure_parent=False,
        fsync=True,
    )


def _try_acquire_lock(lock_dir: str, *, platform_name: str, logger: LoggerProtocol) -> bool:
    try:
        os.mkdir(lock_dir, 0o700)
        try:
            _write_lock_pid(lock_dir)
            return True
        except RECOVERABLE_EXCEPTIONS:
            _release_lock(lock_dir, logger)
            raise
    except FileExistsError:
        pid_value = _read_lock_pid(lock_dir)
        if pid_value is not None and is_pid_running(platform_name=platform_name, pid=pid_value):
            return False
        if pid_value is None and not _lock_without_pid_is_stale(lock_dir):
            return False
        _remove_stale_lock(lock_dir, logger)
        return False


def _release_lock(lock_dir: str, logger: LoggerProtocol) -> None:
    try:
        pid_file = _pid_path(lock_dir)
        if os.path.exists(pid_file):
            os.remove(pid_file)
        if os.path.isdir(lock_dir):
            os.rmdir(lock_dir)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to release software update lock.",
            operation=OPERATION_LOCK_PREPARE,
            details={"lock_dir": lock_dir},
            level="warning",
        )


@contextmanager
def guarded_software_update_lock(
    *,
    base_path: str,
    platform_name: str,
    logger: LoggerProtocol,
) -> Generator[None]:
    lock_dir = resolve_software_update_lock_dir(base_path)
    os.makedirs(os.path.dirname(lock_dir), exist_ok=True)
    deadline = deadline_after(EXTENDED_TIMEOUT_SEC)
    acquired = False
    try:
        while not deadline.expired():
            if _try_acquire_lock(lock_dir, platform_name=platform_name, logger=logger):
                acquired = True
                break
            sleep_seconds(MODERATE_DELAY_SEC)
        if not acquired:
            raise StateError("A SoAI software update is already running.")
        yield
    finally:
        if acquired:
            _release_lock(lock_dir, logger)
