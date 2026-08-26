"""SoAI - Shared atomic filesystem write primitives [backend/core/filesystem/atomic_write_primitives.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import uuid
from contextlib import ExitStack
from dataclasses import dataclass

from core.errors.exception_logging import log_handled_exception
from core.files.secure_open_flags import secure_read_only_open_flags
from core.filesystem.path_coercion import coerce_path
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
    if os.path.exists(temp_path):
        try:
            os.unlink(temp_path)
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
            path,
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
        directory_descriptor = os.open(path, os.O_RDONLY | directory_flag)
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
        os.makedirs(parent, exist_ok=True)
        return
    os.makedirs(parent, mode=mode, exist_ok=True)


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
        backup_resolved = coerce_path(backup_path)
        if os.path.exists(resolved):
            if file_mode is None:
                shutil.copy2(resolved, backup_resolved)
            else:
                _copy_file_to_secure_backup(resolved, backup_resolved, file_mode)
    os.replace(temp_path, resolved)
    if file_mode is not None:
        set_file_mode_after_replace(resolved, file_mode)
    if fsync_parent_directory:
        fsync_directory(parent)


def _copy_file_to_secure_backup(source_path: str, backup_path: str, file_mode: int) -> None:
    temp_path = f"{backup_path}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        descriptor = open_temp_file_descriptor(
            temp_path,
            append=False,
            exclusive=True,
            file_mode=file_mode,
        )
        with os.fdopen(descriptor, "wb") as target_handle:
            with open(source_path, "rb") as source_handle:
                shutil.copyfileobj(source_handle, target_handle)
            target_handle.flush()
            os.fsync(target_handle.fileno())
        os.replace(temp_path, backup_path)
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
    os.link(target.temp_path, target.resolved)
    if file_mode is not None:
        set_file_mode_after_replace(target.resolved, file_mode)
    cleanup_temp_file_on_failure(target.temp_path)
    if fsync_parent_directory:
        fsync_directory(target.parent)
    stack.pop_all()


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
    descriptor = os.open(temp_path, flags, creation_mode)
    if file_mode is None or os.name == "nt":
        return descriptor
    try:
        os.fchmod(descriptor, file_mode)
    except OSError:
        os.close(descriptor)
        raise
    return descriptor


def set_file_mode_after_replace(path: str, file_mode: int) -> None:
    try:
        os.chmod(path, file_mode)
    except OSError as exception:
        log_handled_exception(
            get_logger(ATOMIC_WRITE_LOGGER_NAME),
            exception,
            message="Failed to set file permissions after atomic write (non-critical).",
            operation=ATOMIC_WRITE_OPERATION,
            details={"path": path},
            level="debug",
        )
