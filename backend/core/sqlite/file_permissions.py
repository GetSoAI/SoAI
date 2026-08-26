"""SoAI - SQLite database file permission enforcement [backend/core/sqlite/file_permissions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import SecurityError

__all__ = ("secure_sqlite_file_permissions",)

_SQLITE_FILE_MODE = 0o600
_SQLITE_DIRECTORY_MODE = 0o700
_SQLITE_FILE_SUFFIXES: tuple[str, ...] = ("", "-wal", "-shm", "-journal")


def _is_filesystem_sqlite_path(db_path: str) -> bool:
    normalized = str(db_path or "").strip()
    return bool(normalized and normalized != ":memory:" and not normalized.startswith("file:"))


def _open_existing_no_follow(path: str) -> int | None:
    flags = os.O_RDONLY
    if os.name != "nt":
        flags |= os.O_NOFOLLOW
    try:
        return os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exception:
        raise SecurityError(f"Unable to open SQLite path securely: {path}") from exception


def _create_sqlite_file_if_missing(path: str) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if os.name != "nt":
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, _SQLITE_FILE_MODE)
    except FileExistsError:
        return
    except OSError as exception:
        raise SecurityError(f"Unable to create SQLite file securely: {path}") from exception
    try:
        if os.name == "nt":
            os.chmod(path, _SQLITE_FILE_MODE)
        else:
            os.fchmod(descriptor, _SQLITE_FILE_MODE)
    except OSError as exception:
        raise SecurityError(f"Unable to secure SQLite file permissions: {path}") from exception
    finally:
        os.close(descriptor)


def _secure_windows_path(path: str, *, mode: int, directory: bool) -> None:
    if not os.path.lexists(path):
        return
    if os.path.islink(path):
        raise SecurityError(f"SQLite path must not be a symbolic link: {path}")
    if directory:
        if not os.path.isdir(path):
            raise SecurityError(f"SQLite path is not a directory: {path}")
    elif not os.path.isfile(path):
        raise SecurityError(f"SQLite path is not a regular file: {path}")
    try:
        os.chmod(path, mode)
    except OSError as exception:
        raise SecurityError(f"Unable to secure SQLite path permissions: {path}") from exception


def _secure_open_descriptor(path: str, *, mode: int, directory: bool) -> None:
    if os.name == "nt":
        _secure_windows_path(path, mode=mode, directory=directory)
        return
    descriptor = _open_existing_no_follow(path)
    if descriptor is None:
        return
    try:
        status = os.fstat(descriptor)
        if directory:
            if not stat.S_ISDIR(status.st_mode):
                raise SecurityError(f"SQLite path is not a directory: {path}")
        elif not stat.S_ISREG(status.st_mode):
            raise SecurityError(f"SQLite path is not a regular file: {path}")
        os.fchmod(descriptor, mode)
    except OSError as exception:
        raise SecurityError(f"Unable to secure SQLite path permissions: {path}") from exception
    finally:
        os.close(descriptor)


def secure_sqlite_file_permissions(db_path: str, *, create_missing: bool = False) -> None:
    if not _is_filesystem_sqlite_path(db_path):
        return
    directory = os.path.dirname(db_path)
    if directory:
        _secure_open_descriptor(directory, mode=_SQLITE_DIRECTORY_MODE, directory=True)
    if create_missing:
        _create_sqlite_file_if_missing(db_path)
    for suffix in _SQLITE_FILE_SUFFIXES:
        _secure_open_descriptor(f"{db_path}{suffix}", mode=_SQLITE_FILE_MODE, directory=False)
