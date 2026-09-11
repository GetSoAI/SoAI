"""SoAI - Core atomic filesystem write utilities [backend/core/filesystem/atomic_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import io
import os
import re
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
from core.serialization.json import serialize_json_compact_stable_strict

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput
    from core.types.json import JSONValue

__all__ = (
    "atomic_create_text_content_exclusive",
    "atomic_write_json_content",
    "atomic_write_text",
    "atomic_write_text_content",
    "atomic_text_write_temporary_paths",
)


def atomic_text_write_temporary_paths(path: PathInput) -> tuple[str, ...]:
    resolved = coerce_path(path)
    parent = os.path.dirname(resolved) or os.curdir
    pattern = re.compile(
        rf"{re.escape(os.path.basename(resolved))}\.tmp\.[1-9][0-9]*\.[0-9a-f]{{32}}"
    )
    with os.scandir(parent) as entries:
        return tuple(entry.path for entry in entries if pattern.fullmatch(entry.name))


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
    temp_path = f"{resolved}.partial.{uuid.uuid4().hex}"
    target = AtomicWriteTarget(resolved, temp_path, parent)
    with ExitStack() as stack:
        stack.callback(cleanup_temp_file_on_failure, temp_path)
        file_descriptor = open_temp_file_descriptor(
            temp_path,
            append=False,
            exclusive=True,
            file_mode=file_mode,
        )
        text_handle = os.fdopen(
            file_descriptor,
            "w",
            encoding=encoding or "utf-8",
            errors=errors or "strict",
        )
        if not isinstance(text_handle, io.TextIOBase):
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
    resolved = coerce_path(path)
    parent = os.path.dirname(resolved)
    if ensure_parent:
        ensure_parent_directory(resolved, mode=parent_mode)
    temp_path = f"{resolved}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    target = AtomicWriteTarget(resolved, temp_path, parent)
    with ExitStack() as stack:
        stack.callback(cleanup_temp_file_on_failure, temp_path)
        if mode not in {"w", "a"}:
            raise ValidationError("Text atomic writes only support mode 'w' or 'a'.")
        resolved_encoding = encoding or "utf-8"
        resolved_errors = errors or "strict"
        append_existing_file = mode == "a" and os.path.exists(resolved)
        if append_existing_file:
            shutil.copy2(resolved, temp_path)
        file_descriptor = open_temp_file_descriptor(
            temp_path,
            append=mode == "a",
            exclusive=not append_existing_file,
            file_mode=file_mode,
        )
        text_handle = os.fdopen(
            file_descriptor,
            mode,
            encoding=resolved_encoding,
            errors=resolved_errors,
        )
        if not isinstance(text_handle, io.TextIOBase):
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
