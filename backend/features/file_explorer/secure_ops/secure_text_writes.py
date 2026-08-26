"""SoAI - Symlink-safe text replacement for file explorer writes [backend/features/file_explorer/secure_ops/secure_text_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
import uuid

from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.files.path_policy import ensure_path_within_base_lexical
from core.filesystem.path_coercion import coerce_path

__all__ = ("write_text_no_symlink_atomic",)


def _open_child_directory(parent_fd: int, name: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exception:
        raise SecurityError(
            "Cannot write through symbolic link path components.",
            operation="file_explorer.write_text_atomic",
        ) from exception


def _open_root_directory(root_path: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        return os.open(root_path, flags)
    except OSError as exception:
        raise SecurityError(
            "Cannot open file explorer root directory.",
            operation="file_explorer.write_text_atomic",
        ) from exception


def _open_parent_directory(root_path: str, real_path: str) -> tuple[int, int, str]:
    root_resolved = coerce_path(root_path)
    target_resolved = ensure_path_within_base_lexical(
        root_resolved,
        coerce_path(real_path),
        description="File explorer path",
        error_cls=SecurityError,
    )
    relative = os.path.relpath(target_resolved, root_resolved)
    parts = tuple(part for part in relative.split(os.sep) if part)
    if not parts or any(part in {".", ".."} for part in parts):
        raise SecurityError(
            "Invalid file explorer target path.",
            operation="file_explorer.write_text_atomic",
        )
    root_fd = _open_root_directory(root_resolved)
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            next_fd = _open_child_directory(current_fd, part)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
    except (OSError, SecurityError, StateError, ValidationError):
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)
        raise
    return root_fd, current_fd, parts[-1]


def _read_existing_mode(parent_fd: int, target_name: str) -> int | None:
    try:
        stat_info = os.stat(target_name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exception:
        raise StateError(
            f"Cannot inspect target file: {exception}",
            operation="file_explorer.write_text_atomic",
        ) from exception
    if stat.S_ISLNK(stat_info.st_mode):
        raise SecurityError(
            "Cannot write symbolic link target.",
            operation="file_explorer.write_text_atomic",
        )
    if not stat.S_ISREG(stat_info.st_mode):
        raise ValidationError(
            "Target path is not a regular file.",
            operation="file_explorer.write_text_atomic",
        )
    return stat.S_IMODE(stat_info.st_mode)


def _write_temp_file(parent_fd: int, content: bytes, existing_mode: int | None) -> str:
    temp_name = f".soai_fe_.{uuid.uuid4().hex}.tmp"
    mode = existing_mode if existing_mode is not None else 0o666
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    file_fd = os.open(temp_name, flags, mode, dir_fd=parent_fd)
    try:
        offset = 0
        while offset < len(content):
            written = os.write(file_fd, content[offset:])
            if written <= 0:
                raise OSError("Failed to write file content.")
            offset += written
        os.fsync(file_fd)
    except OSError:
        os.unlink(temp_name, dir_fd=parent_fd)
        raise
    finally:
        os.close(file_fd)
    return temp_name


def write_text_no_symlink_atomic(root_path: str, real_path: str, content: str) -> None:
    encoded = content.encode("utf-8")
    root_fd, parent_fd, target_name = _open_parent_directory(root_path, real_path)
    temp_name = ""
    try:
        existing_mode = _read_existing_mode(parent_fd, target_name)
        temp_name = _write_temp_file(parent_fd, encoded, existing_mode)
        os.replace(temp_name, target_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        temp_name = ""
        os.fsync(parent_fd)
    finally:
        if temp_name:
            os.unlink(temp_name, dir_fd=parent_fd)
        if parent_fd != root_fd:
            os.close(parent_fd)
        os.close(root_fd)
