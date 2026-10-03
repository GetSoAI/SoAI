"""SoAI - Core atomic binary filesystem write utilities [backend/core/filesystem/atomic_binary_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
from collections.abc import Callable
from contextlib import ExitStack
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_write_primitives import (
    AtomicWriteTarget,
    allocate_atomic_temporary_file,
    cleanup_temp_file_on_failure,
    copy_existing_file_to_descriptor,
    ensure_parent_directory,
    finalize_atomic_write_create_and_clear_callbacks,
    finalize_atomic_write_replace_and_clear_callbacks,
)
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.path_coercion import coerce_path, normalize_filesystem_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = (
    "atomic_write_binary",
    "atomic_write_binary_content",
)


def _finalize_binary_write(
    stack: ExitStack,
    target: AtomicWriteTarget,
    *,
    backup_path: str | None,
    file_mode: int | None,
    fsync_parent_directory: bool,
    exclusive: bool,
) -> None:
    if exclusive:
        finalize_atomic_write_create_and_clear_callbacks(
            stack,
            target,
            file_mode=file_mode,
            fsync_parent_directory=fsync_parent_directory,
        )
        return
    finalize_atomic_write_replace_and_clear_callbacks(
        stack,
        target,
        backup_path=backup_path,
        file_mode=file_mode,
        fsync_parent_directory=fsync_parent_directory,
    )


def atomic_write_binary(
    path: PathInput,
    writer: Callable[[io.BufferedIOBase], None],
    *,
    mode: str = "wb",
    ensure_parent: bool = True,
    fsync: bool = True,
    backup_path: str | None = None,
    file_mode: int | None = None,
    fsync_parent_directory: bool = False,
    exclusive: bool = False,
) -> None:
    resolved = coerce_path(path)
    if mode not in {"wb", "ab"}:
        raise ValidationError("Binary atomic writes only support mode 'wb' or 'ab'.")
    if exclusive and (mode != "wb" or backup_path is not None):
        raise ValidationError("Exclusive binary atomic writes require mode 'wb' without a backup.")
    parent = os.path.dirname(resolved)
    if ensure_parent:
        ensure_parent_directory(resolved, mode=None)
    file_descriptor, temp_path = allocate_atomic_temporary_file(resolved, file_mode=file_mode)
    target = AtomicWriteTarget(resolved, temp_path, parent)
    with ExitStack() as stack:
        stack.callback(cleanup_temp_file_on_failure, temp_path)
        try:
            if mode == "ab" and os.path.exists(normalize_filesystem_path(resolved)):
                copy_existing_file_to_descriptor(
                    resolved, file_descriptor, preserve_permissions=file_mode is None
                )
            binary_handle = os.fdopen(file_descriptor, mode)
        except (OSError, ValueError):
            os.close(file_descriptor)
            raise
        if not isinstance(binary_handle, io.BufferedIOBase):
            binary_handle.close()
            raise ValidationError("Atomic binary writer failed to open a binary stream.")
        with binary_handle:
            writer(binary_handle)
            if fsync:
                flush_and_fsync_file(binary_handle)
        _finalize_binary_write(
            stack,
            target,
            backup_path=backup_path,
            file_mode=file_mode,
            fsync_parent_directory=fsync_parent_directory,
            exclusive=exclusive,
        )


def atomic_write_binary_content(
    path: PathInput,
    content: bytes,
    *,
    ensure_parent: bool = True,
    fsync: bool = True,
    file_mode: int | None = None,
    fsync_parent_directory: bool = False,
) -> None:
    def writer(handle: io.BufferedIOBase) -> None:
        handle.write(content)

    atomic_write_binary(
        path,
        writer,
        mode="wb",
        ensure_parent=ensure_parent,
        fsync=fsync,
        file_mode=file_mode,
        fsync_parent_directory=fsync_parent_directory,
    )
