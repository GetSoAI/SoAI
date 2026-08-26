"""SoAI - Core atomic binary filesystem write utilities [backend/core/filesystem/atomic_binary_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import shutil
import uuid
from collections.abc import Callable
from contextlib import ExitStack
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.filesystem.atomic_write_primitives import (
    AtomicWriteTarget,
    cleanup_temp_file_on_failure,
    ensure_parent_directory,
    finalize_atomic_write_create_and_clear_callbacks,
    finalize_atomic_write_replace_and_clear_callbacks,
    open_temp_file_descriptor,
)
from core.filesystem.file_sync import flush_and_fsync_file
from core.filesystem.path_coercion import coerce_path

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
    temp_path = f"{resolved}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    target = AtomicWriteTarget(resolved, temp_path, parent)
    with ExitStack() as stack:
        stack.callback(cleanup_temp_file_on_failure, temp_path)
        append_existing_file = mode == "ab" and os.path.exists(resolved)
        if append_existing_file:
            shutil.copy2(resolved, temp_path)
        file_descriptor = open_temp_file_descriptor(
            temp_path,
            append=mode == "ab",
            exclusive=not append_existing_file,
            file_mode=file_mode,
        )
        binary_handle = os.fdopen(file_descriptor, mode)
        if not isinstance(binary_handle, io.BufferedIOBase):
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
