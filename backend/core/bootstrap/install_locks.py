"""SoAI - Directory lock helpers for install flows [backend/core/bootstrap/install_locks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ctypes
import os
import secrets
import time
from collections.abc import Generator
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass

import psutil

from core.bootstrap.install_filesystem import rmdir_if_exists, unlink_if_exists
from core.errors.exceptions import ConflictError, SoAITimeoutError, StateError
from core.files.windows_handle_operations import close_windows_handle
from core.filesystem.open_files import create_binary_owner_only
from core.filesystem.path_coercion import normalize_filesystem_path
from core.runtime.process_identity_signals import read_process_create_time_ms
from core.system.pid_liveness import pid_is_running
from core.system.windows_ctypes import last_windows_error, load_kernel32
from core.timing.sleep import sleep_seconds

__all__ = (
    "INSTALL_LOCK_ENV",
    "INSTALL_LOCK_TOKEN_ENV",
    "INSTALL_LOCK_OWNER_START_ENV",
    "InstallDirectoryLock",
    "guard_windows_installer_gate",
    "inherited_install_lock_is_valid",
    "publish_install_lock_environment",
    "acquire_lock_dir",
    "lock_dir_has_live_owner",
    "read_lock_pid",
    "read_lock_token",
    "release_lock_dir",
    "wait_for_lock_dir_clear",
)

INSTALL_LOCK_ENV = "SOAI_INSTALL_LOCK_HELD_PATH"
INSTALL_LOCK_TOKEN_ENV = "SOAI_INSTALL_LOCK_HELD_TOKEN"
INSTALL_LOCK_OWNER_START_ENV = "SOAI_INSTALL_LOCK_OWNER_START_MS"
LOCK_TIMEOUT_SECONDS = 1200.0
LOCK_TOKEN_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class InstallDirectoryLock:
    path: str
    token: str
    device: int
    inode: int


def acquire_lock_dir(lock_dir: str) -> InstallDirectoryLock:
    resolved_lock_dir = os.path.abspath(lock_dir)
    try:
        owner_start_ms = read_process_create_time_ms(psutil.Process())
    except psutil.Error as exception:
        raise StateError(
            "Cannot verify installation process ownership before creating its lock."
        ) from exception
    parent_dir = os.path.dirname(resolved_lock_dir)
    if parent_dir:
        os.makedirs(normalize_filesystem_path(parent_dir), exist_ok=True)
    start = time.monotonic()
    missing_pid_started: float | None = None
    while True:
        try:
            os.mkdir(normalize_filesystem_path(resolved_lock_dir))
            identity = os.stat(normalize_filesystem_path(resolved_lock_dir), follow_symlinks=False)
            try:
                _write_pid_file(resolved_lock_dir)
                _write_token_file(resolved_lock_dir)
                with create_binary_owner_only(
                    os.path.join(resolved_lock_dir, "owner-start-ms")
                ) as handle:
                    handle.write(f"{owner_start_ms}\n".encode("ascii"))
            except OSError:
                current = os.stat(
                    normalize_filesystem_path(resolved_lock_dir), follow_symlinks=False
                )
                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    _remove_stale_lock(resolved_lock_dir)
                raise
            token = read_lock_token(resolved_lock_dir)
            if token is None:
                raise StateError("Install lock publication did not produce an ownership token.")
            identity = os.stat(normalize_filesystem_path(resolved_lock_dir), follow_symlinks=False)
            return InstallDirectoryLock(resolved_lock_dir, token, identity.st_dev, identity.st_ino)
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


def release_lock_dir(lock: InstallDirectoryLock) -> None:
    lock_dir = lock.path
    identity = os.stat(normalize_filesystem_path(lock_dir), follow_symlinks=False)
    if (identity.st_dev, identity.st_ino) != (lock.device, lock.inode) or read_lock_token(
        lock_dir
    ) != lock.token:
        raise StateError("Install lock ownership changed; foreign lock evidence has been retained.")
    pid_file = os.path.join(lock_dir, "pid")
    token_file = os.path.join(lock_dir, "token")
    unlink_if_exists(os.path.join(lock_dir, "owner-start-ms"))
    unlink_if_exists(token_file)
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
    with open(
        normalize_filesystem_path(pid_file), "x", encoding="utf-8", errors="strict"
    ) as handle:
        handle.write(f"{os.getpid()}\n")


def _write_token_file(lock_dir: str) -> None:
    token_file = os.path.join(lock_dir, "token")
    token = f"{secrets.token_hex(LOCK_TOKEN_HEX_LENGTH // 2)}\n".encode("ascii")
    with create_binary_owner_only(token_file) as handle:
        handle.write(token)


def _clear_stale_lock(lock_dir: str, *, missing_pid_started: float | None) -> float | None:
    pid = read_lock_pid(lock_dir)
    if pid is not None:
        if not pid_is_running(pid):
            raise StateError(
                "An abandoned install lock requires verified recovery; its evidence has been retained."
            )
        return None
    if missing_pid_started is None:
        return time.monotonic()
    return missing_pid_started


def _remove_stale_lock(lock_dir: str) -> None:
    unlink_if_exists(os.path.join(lock_dir, "owner-start-ms"))
    unlink_if_exists(os.path.join(lock_dir, "token"))
    unlink_if_exists(os.path.join(lock_dir, "pid"))
    rmdir_if_exists(lock_dir)


def read_lock_pid(lock_dir: str) -> int | None:
    pid_file = os.path.join(lock_dir, "pid")
    text = ""
    read_succeeded = False
    try:
        with open(normalize_filesystem_path(pid_file), encoding="utf-8", errors="strict") as handle:
            text = handle.readline().strip()
        read_succeeded = True
    except (OSError, UnicodeError):
        read_succeeded = False
    if not read_succeeded:
        return None
    if not text.isdigit():
        return None
    return int(text)


def read_lock_token(lock_dir: str) -> str | None:
    token_file = os.path.join(lock_dir, "token")
    token = ""
    read_succeeded = False
    try:
        with open(
            normalize_filesystem_path(token_file), encoding="utf-8", errors="strict"
        ) as handle:
            token = handle.readline().strip()
        read_succeeded = True
    except (OSError, UnicodeError):
        read_succeeded = False
    if not read_succeeded:
        return None
    if len(token) != LOCK_TOKEN_HEX_LENGTH:
        return None
    if any(character not in "0123456789abcdef" for character in token):
        return None
    return token


def inherited_install_lock_is_valid(lock_dir: str) -> bool:
    inherited_path = os.environ.get(INSTALL_LOCK_ENV, "")
    if not inherited_path or os.path.normcase(os.path.abspath(inherited_path)) != os.path.normcase(
        os.path.abspath(lock_dir)
    ):
        return False
    inherited_token = os.environ.get(INSTALL_LOCK_TOKEN_ENV, "")
    token = read_lock_token(lock_dir)
    owner_pid = read_lock_pid(lock_dir)
    start_value = os.environ.get(INSTALL_LOCK_OWNER_START_ENV, "")
    if not inherited_token or token is None or owner_pid is None or not start_value.isdigit():
        return False
    if not secrets.compare_digest(inherited_token, token):
        return False
    valid_parent = False
    try:
        valid_parent = any(
            parent.pid == owner_pid and read_process_create_time_ms(parent) == int(start_value)
            for parent in psutil.Process().parents()
        )
    except psutil.Error:
        valid_parent = False
    return valid_parent


def publish_install_lock_environment(lock: InstallDirectoryLock) -> None:
    os.environ[INSTALL_LOCK_ENV] = lock.path
    os.environ[INSTALL_LOCK_TOKEN_ENV] = lock.token
    os.environ[INSTALL_LOCK_OWNER_START_ENV] = str(read_process_create_time_ms(psutil.Process()))


@contextmanager
def guard_windows_installer_gate(*, inherited: bool = False) -> Generator[None]:
    mutex_handle: int | None = None
    if os.name == "nt":
        kernel = load_kernel32()
        if inherited:
            open_mutex = kernel.OpenMutexW
            open_mutex.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
            open_mutex.restype = wintypes.HANDLE
            handle = open_mutex(0x00100000, False, "Global\\SoAI.WindowsInstaller.V1")
            if not handle:
                raise StateError("The verified parent installer gate is missing.")
        else:
            create_mutex = kernel.CreateMutexW
            create_mutex.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            create_mutex.restype = wintypes.HANDLE
            handle = create_mutex(None, False, "Global\\SoAI.WindowsInstaller.V1")
            error_code = last_windows_error()
            if not handle:
                raise StateError(
                    "Cannot open the Windows installer admission gate.",
                    details={"windows_error": error_code},
                )
            if error_code == 183:
                close_windows_handle(int(handle))
                raise ConflictError("Another SoAI installer or repair operation is active.")
        mutex_handle = int(handle)
    try:
        yield
    finally:
        if mutex_handle is not None:
            close_windows_handle(mutex_handle)
