"""SoAI - Secure file explorer read operations [backend/features/file_explorer/secure_ops/secure_read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import os

from core.errors.exceptions import NotFoundError, SecurityError, StateError, ValidationError
from core.filesystem.open_files import open_binary

__all__ = ("read_bytes_sample", "read_text_file")


def read_text_file(real_path: str, *, max_bytes: int, allow_symlinks: bool) -> str:
    if os.name == "nt":
        return _read_text_file_windows(
            real_path,
            max_bytes=max_bytes,
            allow_symlinks=allow_symlinks,
        )
    return _read_text_file_posix(real_path, max_bytes=max_bytes, allow_symlinks=allow_symlinks)


def read_bytes_sample(real_path: str, *, max_bytes: int, allow_symlinks: bool) -> bytes:
    if os.name == "nt":
        return _read_bytes_sample_windows(
            real_path,
            max_bytes=max_bytes,
            allow_symlinks=allow_symlinks,
        )
    return _read_bytes_sample_posix(real_path, max_bytes=max_bytes, allow_symlinks=allow_symlinks)


def _read_bytes_sample_windows(real_path: str, *, max_bytes: int, allow_symlinks: bool) -> bytes:
    if not allow_symlinks and os.path.islink(real_path):
        raise SecurityError(
            "Cannot read symbolic link target.",
            operation="file_explorer.read_bytes_sample",
        )
    try:
        with open_binary(real_path, mode="rb") as file_handle:
            return file_handle.read(max_bytes)
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"File not found: '{os.path.basename(real_path)}'.",
            operation="file_explorer.read_bytes_sample",
        ) from exception


def _read_bytes_sample_posix(real_path: str, *, max_bytes: int, allow_symlinks: bool) -> bytes:
    open_flags = os.O_RDONLY
    if not allow_symlinks:
        open_flags |= os.O_NOFOLLOW
    try:
        file_fd = os.open(real_path, open_flags)
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"File not found: '{os.path.basename(real_path)}'.",
            operation="file_explorer.read_bytes_sample",
        ) from exception
    except OSError as exception:
        if exception.errno == errno.ELOOP:
            raise SecurityError(
                "Cannot read symbolic link target.",
                operation="file_explorer.read_bytes_sample",
            ) from exception
        raise StateError(
            f"Cannot open file: {exception}",
            operation="file_explorer.read_bytes_sample",
        ) from exception
    try:
        return os.read(file_fd, max_bytes)
    finally:
        os.close(file_fd)


def _read_text_file_windows(real_path: str, *, max_bytes: int, allow_symlinks: bool) -> str:
    if not allow_symlinks and os.path.islink(real_path):
        raise SecurityError(
            "Cannot read symbolic link target.",
            operation="file_explorer.read_text",
        )
    try:
        with open_binary(real_path, mode="rb") as file_handle:
            raw = file_handle.read(max_bytes + 1)
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"File not found: '{os.path.basename(real_path)}'.",
            operation="file_explorer.read_text",
        ) from exception
    return _decode_limited_text(raw, max_bytes=max_bytes)


def _read_text_file_posix(real_path: str, *, max_bytes: int, allow_symlinks: bool) -> str:
    open_flags = os.O_RDONLY
    if not allow_symlinks:
        open_flags |= os.O_NOFOLLOW
    try:
        file_fd = os.open(real_path, open_flags)
    except FileNotFoundError as exception:
        raise NotFoundError(
            f"File not found: '{os.path.basename(real_path)}'.",
            operation="file_explorer.read_text",
        ) from exception
    except OSError as exception:
        if exception.errno == errno.ELOOP:
            raise SecurityError(
                "Cannot read symbolic link target.",
                operation="file_explorer.read_text",
            ) from exception
        raise StateError(
            f"Cannot open file: {exception}",
            operation="file_explorer.read_text",
        ) from exception
    try:
        raw = os.read(file_fd, max_bytes + 1)
    finally:
        os.close(file_fd)
    return _decode_limited_text(raw, max_bytes=max_bytes)


def _decode_limited_text(raw: bytes, *, max_bytes: int) -> str:
    if len(raw) > max_bytes:
        raise ValidationError(
            f"File exceeds preview limit of {max_bytes} bytes.",
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exception:
        raise ValidationError(
            "File preview is only available for UTF-8 text files.",
        ) from exception
