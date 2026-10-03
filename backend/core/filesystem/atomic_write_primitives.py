"""SoAI - Shared atomic filesystem write primitives [backend/core/filesystem/atomic_write_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
from contextlib import ExitStack
from dataclasses import dataclass

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.files.secure_open_flags import secure_read_only_open_flags
from core.filesystem.atomic_write_names import atomic_temporary_path
from core.filesystem.exclusive_rename import rename_file_without_replacement
from core.filesystem.path_coercion import coerce_path, normalize_filesystem_path
from core.logging.trace import get_logger

__all__ = (
    "ATOMIC_WRITE_LOGGER_NAME",
    "ATOMIC_WRITE_OPERATION",
    "AtomicWriteTarget",
    "cleanup_temp_file_on_failure",
    "ensure_parent_directory",
    "finalize_atomic_write_replace",
    "finalize_atomic_write_replace_and_clear_callbacks",
    "finalize_atomic_write_create_and_clear_callbacks",
    "fsync_directory",
    "open_temp_file_descriptor",
    "allocate_atomic_temporary_file",
    "copy_existing_file_to_descriptor",
    "set_file_mode_after_replace",
)

ATOMIC_WRITE_LOGGER_NAME = "SoAI.core.filesystem.atomic_writes"
ATOMIC_WRITE_OPERATION = "core.filesystem.atomic_writes.cleanup"


@dataclass(frozen=True, slots=True)
class AtomicWriteTarget:
    resolved: str
    temp_path: str
    parent: str


def cleanup_temp_file_on_failure(temp_path: str) -> None:
    filesystem_path = normalize_filesystem_path(temp_path)
    if os.path.exists(filesystem_path):
        try:
            os.unlink(filesystem_path)
        except OSError as exception:
            log_handled_exception(
                get_logger(ATOMIC_WRITE_LOGGER_NAME),
                exception,
                message="Failed to clean up temp file during atomic write failure (non-critical).",
                operation=ATOMIC_WRITE_OPERATION,
                details={"temp_path": temp_path},
                level="debug",
            )


def fsync_directory(path: str, *, strict: bool = False) -> None:
    if not path:
        return
    if strict:
        if os.name == "nt":
            return
        strict_directory_descriptor = os.open(
            normalize_filesystem_path(path),
            secure_read_only_open_flags(directory=True),
        )
        try:
            os.fsync(strict_directory_descriptor)
        finally:
            os.close(strict_directory_descriptor)
        return
    try:
        directory_flag = os.O_DIRECTORY
    except AttributeError:
        return
    directory_descriptor: int | None = None
    try:
        directory_descriptor = os.open(
            normalize_filesystem_path(path), os.O_RDONLY | directory_flag
        )
        os.fsync(directory_descriptor)
    except OSError as exception:
        log_handled_exception(
            get_logger(ATOMIC_WRITE_LOGGER_NAME),
            exception,
            message="Failed to fsync directory after atomic write (non-critical).",
            operation=ATOMIC_WRITE_OPERATION,
            details={"path": path},
            level="debug",
        )
    finally:
        if directory_descriptor is not None:
            try:
                os.close(directory_descriptor)
            except OSError as exception:
                log_handled_exception(
                    get_logger(ATOMIC_WRITE_LOGGER_NAME),
                    exception,
                    message="Failed to close directory handle after atomic write (non-critical).",
                    operation=ATOMIC_WRITE_OPERATION,
                    details={"path": path},
                    level="debug",
                )


def ensure_parent_directory(path: str, *, mode: int | None) -> None:
    parent = os.path.dirname(path)
    if not parent:
        return
    if mode is None:
        os.makedirs(normalize_filesystem_path(parent), exist_ok=True)
        return
    os.makedirs(normalize_filesystem_path(parent), mode=mode, exist_ok=True)


def finalize_atomic_write_replace(
    *,
    resolved: str,
    temp_path: str,
    parent: str,
    backup_path: str | None,
    file_mode: int | None,
    fsync_parent_directory: bool,
) -> None:
    if backup_path:
        backup_resolved = normalize_filesystem_path(coerce_path(backup_path))
        if os.path.exists(normalize_filesystem_path(resolved)):
            _copy_file_to_secure_backup(resolved, backup_resolved, file_mode)
    os.replace(normalize_filesystem_path(temp_path), normalize_filesystem_path(resolved))
    if file_mode is not None:
        set_file_mode_after_replace(resolved, file_mode)
    if fsync_parent_directory:
        fsync_directory(parent)


def _copy_file_to_secure_backup(source_path: str, backup_path: str, file_mode: int | None) -> None:
    descriptor, temp_path = allocate_atomic_temporary_file(backup_path, file_mode=file_mode)
    try:
        try:
            target_handle = os.fdopen(descriptor, "wb")
        except (OSError, ValueError):
            os.close(descriptor)
            raise
        with target_handle:
            with open(normalize_filesystem_path(source_path), "rb") as source_handle:
                shutil.copyfileobj(source_handle, target_handle)
            target_handle.flush()
            if file_mode is None:
                shutil.copystat(
                    normalize_filesystem_path(source_path), normalize_filesystem_path(temp_path)
                )
            os.fsync(target_handle.fileno())
        os.replace(normalize_filesystem_path(temp_path), normalize_filesystem_path(backup_path))
        if file_mode is not None:
            set_file_mode_after_replace(backup_path, file_mode)
    finally:
        cleanup_temp_file_on_failure(temp_path)


def finalize_atomic_write_replace_and_clear_callbacks(
    stack: ExitStack,
    target: AtomicWriteTarget,
    *,
    backup_path: str | None,
    file_mode: int | None,
    fsync_parent_directory: bool,
) -> None:
    finalize_atomic_write_replace(
        resolved=target.resolved,
        temp_path=target.temp_path,
        parent=target.parent,
        backup_path=backup_path,
        file_mode=file_mode,
        fsync_parent_directory=fsync_parent_directory,
    )
    stack.pop_all()


def finalize_atomic_write_create_and_clear_callbacks(
    stack: ExitStack,
    target: AtomicWriteTarget,
    *,
    file_mode: int | None,
    fsync_parent_directory: bool,
) -> None:
    rename_file_without_replacement(target.temp_path, target.resolved)
    stack.pop_all()
    if file_mode is not None:
        set_file_mode_after_replace(target.resolved, file_mode)
    if fsync_parent_directory:
        fsync_directory(target.parent)


def open_temp_file_descriptor(
    temp_path: str,
    *,
    append: bool,
    exclusive: bool,
    file_mode: int | None,
) -> int:
    flags = os.O_WRONLY | os.O_CREAT
    flags |= os.O_APPEND if append else os.O_TRUNC
    if exclusive:
        flags |= os.O_EXCL
    creation_mode = file_mode if file_mode is not None else 0o666
    descriptor = os.open(normalize_filesystem_path(temp_path), flags, creation_mode)
    if file_mode is None or os.name == "nt":
        return descriptor
    try:
        os.fchmod(descriptor, file_mode)
    except OSError:
        os.close(descriptor)
        cleanup_temp_file_on_failure(temp_path)
        raise
    return descriptor


def set_file_mode_after_replace(path: str, file_mode: int) -> None:
    try:
        os.chmod(normalize_filesystem_path(path), file_mode)
    except OSError as exception:
        log_handled_exception(
            get_logger(ATOMIC_WRITE_LOGGER_NAME),
            exception,
            message="Failed to set file permissions after atomic write (non-critical).",
            operation=ATOMIC_WRITE_OPERATION,
            details={"path": path},
            level="debug",
        )


def allocate_atomic_temporary_file(
    destination: str, *, file_mode: int | None, partial: bool = False
) -> tuple[int, str]:
    for attempt in range(3):
        temp_path = atomic_temporary_path(destination, partial=partial)
        try:
            descriptor = open_temp_file_descriptor(
                temp_path, append=False, exclusive=True, file_mode=file_mode
            )
        except FileExistsError:
            if attempt == 2:
                raise
        else:
            return descriptor, temp_path
    raise StateError("Atomic allocation exhausted without an explicit outcome.")


def copy_existing_file_to_descriptor(
    source: str, descriptor: int, *, preserve_permissions: bool
) -> None:
    with open(normalize_filesystem_path(source), "rb") as source_handle:
        if preserve_permissions and os.name != "nt":
            os.fchmod(descriptor, os.fstat(source_handle.fileno()).st_mode & 0o7777)
        while content := source_handle.read(1024 * 1024):
            remaining = memoryview(content)
            while remaining:
                written = os.write(descriptor, remaining)
                if written <= 0:
                    raise OSError("Atomic append could not copy existing bytes.")
                remaining = remaining[written:]
