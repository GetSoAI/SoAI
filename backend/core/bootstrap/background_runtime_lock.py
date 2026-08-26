"""SoAI - Launcher runtime lock ownership [backend/core/bootstrap/background_runtime_lock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.bootstrap.launch_console import emit
from core.filesystem.open_files import open_text

__all__ = (
    "release_launcher_runtime_lock_if_owned",
    "transfer_launcher_runtime_lock",
)

LAUNCHER_RUNTIME_LOCK_DIR_ENV: str = "SOAI_LAUNCHER_RUNTIME_LOCK_DIR"


def transfer_launcher_runtime_lock(child_pid: int) -> bool:
    lock_dir = os.environ.get(LAUNCHER_RUNTIME_LOCK_DIR_ENV, "")
    if not lock_dir:
        return True
    if not os.path.isdir(lock_dir):
        emit("ERROR", f"Launcher runtime lock directory is missing: {lock_dir}")
        return False
    pid_file_path = os.path.join(lock_dir, "pid")
    transfer_failed = False
    try:
        with open_text(
            pid_file_path,
            mode="w",
            encoding="utf-8",
            errors="strict",
        ) as handle:
            handle.write(f"{child_pid}\n")
    except OSError as exception:
        emit(
            "ERROR",
            f"Failed to transfer launcher runtime lock to background process: {type(exception).__name__}: {exception}",
        )
        transfer_failed = True
    if transfer_failed:
        return False
    return True


def release_launcher_runtime_lock_if_owned() -> None:
    lock_dir = os.environ.get(LAUNCHER_RUNTIME_LOCK_DIR_ENV, "")
    if not lock_dir:
        return
    if not os.path.isdir(lock_dir):
        return
    pid_file_path = os.path.join(lock_dir, "pid")
    try:
        with open_text(
            pid_file_path,
            mode="r",
            encoding="utf-8",
            errors="replace",
        ) as handle:
            raw_pid = handle.read().strip()
    except FileNotFoundError:
        return
    if raw_pid != str(os.getpid()):
        return
    try:
        os.unlink(pid_file_path)
    except FileNotFoundError:
        return
    os.rmdir(lock_dir)
