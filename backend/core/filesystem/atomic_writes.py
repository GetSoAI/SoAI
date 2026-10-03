"""SoAI - Core atomic filesystem write utilities [backend/core/filesystem/atomic_writes.py]"""
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
from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput
    from core.types.json import JSONValue

__all__ = (
    "atomic_create_text_content_exclusive",
    "atomic_write_json_content",
    "atomic_write_text",
    "atomic_write_text_content",
)


def atomic_create_text_content_exclusive(
    path: PathInput,
    content: str,
    *,
    encoding: str | None = "utf-8",
    errors: str | None = "strict",
    ensure_parent: bool = True,
    parent_mode: int | None = None,
    fsync: bool = True,
    file_mode: int | None = None,
    fsync_parent_directory: bool = False,
) -> None:
    resolved = coerce_path(path)
    parent = os.path.dirname(resolved)
    if ensure_parent:
        ensure_parent_directory(resolved, mode=parent_mode)
    file_descriptor, temp_path = allocate_atomic_temporary_file(
        resolved, file_mode=file_mode, partial=True
    )
    target = AtomicWriteTarget(resolved, temp_path, parent)
    with ExitStack() as stack:
        stack.callback(cleanup_temp_file_on_failure, temp_path)
        try:
            text_handle = os.fdopen(
                file_descriptor, "w", encoding=encoding or "utf-8", errors=errors or "strict"
            )
        except (OSError, ValueError):
            os.close(file_descriptor)
            raise
        if not isinstance(text_handle, io.TextIOBase):
            text_handle.close()
            raise ValidationError("Exclusive text writer failed to open a text stream.")
        with text_handle:
            text_handle.write(content)
            if fsync:
                flush_and_fsync_file(text_handle)
        finalize_atomic_write_create_and_clear_callbacks(
            stack,
            target,
            file_mode=file_mode,
            fsync_parent_directory=fsync_parent_directory,
        )


def atomic_write_text(
    path: PathInput,
    writer: Callable[[io.TextIOBase], None],
    *,
    mode: str = "w",
    encoding: str | None = "utf-8",
    errors: str | None = "strict",
    ensure_parent: bool = True,
    parent_mode: int | None = None,
    fsync: bool = True,
    backup_path: str | None = None,
    file_mode: int | None = None,
    fsync_parent_directory: bool = False,
) -> None:
    if mode not in {"w", "a"}:
        raise ValidationError("Text atomic writes only support mode 'w' or 'a'.")
    resolved = coerce_path(path)
    parent = os.path.dirname(resolved)
    if ensure_parent:
        ensure_parent_directory(resolved, mode=parent_mode)
    file_descriptor, temp_path = allocate_atomic_temporary_file(resolved, file_mode=file_mode)
    target = AtomicWriteTarget(resolved, temp_path, parent)
    with ExitStack() as stack:
        stack.callback(cleanup_temp_file_on_failure, temp_path)
        resolved_encoding = encoding or "utf-8"
        resolved_errors = errors or "strict"
        try:
            if mode == "a" and os.path.exists(normalize_filesystem_path(resolved)):
                copy_existing_file_to_descriptor(
                    resolved, file_descriptor, preserve_permissions=file_mode is None
                )
            text_handle = os.fdopen(
                file_descriptor, mode, encoding=resolved_encoding, errors=resolved_errors
            )
        except (OSError, ValueError):
            os.close(file_descriptor)
            raise
        if not isinstance(text_handle, io.TextIOBase):
            text_handle.close()
            raise ValidationError("Atomic text writer failed to open a text stream.")
        with text_handle:
            writer(text_handle)
            if fsync:
                flush_and_fsync_file(text_handle)
        finalize_atomic_write_replace_and_clear_callbacks(
            stack,
            target,
            backup_path=backup_path,
            file_mode=file_mode,
            fsync_parent_directory=fsync_parent_directory,
        )


def atomic_write_text_content(
    path: PathInput,
    content: str,
    *,
    encoding: str | None = "utf-8",
    errors: str | None = "strict",
    ensure_parent: bool = True,
    parent_mode: int | None = None,
    fsync: bool = True,
    file_mode: int | None = None,
    fsync_parent_directory: bool = False,
) -> None:
    def writer(handle: io.TextIOBase) -> None:
        handle.write(content)

    atomic_write_text(
        path,
        writer,
        mode="w",
        encoding=encoding,
        errors=errors,
        ensure_parent=ensure_parent,
        parent_mode=parent_mode,
        fsync=fsync,
        file_mode=file_mode,
        fsync_parent_directory=fsync_parent_directory,
    )


def atomic_write_json_content(
    path: PathInput,
    payload: JSONValue,
    *,
    ensure_ascii: bool = False,
    fsync: bool = True,
    fsync_parent_directory: bool = False,
) -> None:
    atomic_write_text_content(
        path,
        serialize_json_compact_stable_strict(payload, ensure_ascii=ensure_ascii),
        encoding="utf-8",
        errors="strict",
        fsync=fsync,
        fsync_parent_directory=fsync_parent_directory,
    )
