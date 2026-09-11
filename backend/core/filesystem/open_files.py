"""SoAI - Core filesystem open helpers [backend/core/filesystem/open_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import io
import os
import stat
from typing import TYPE_CHECKING, Literal, overload

from core.errors.exceptions import ValidationError
from core.files.secure_open_flags import secure_read_only_open_flags
from core.filesystem.path_coercion import coerce_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = (
    "create_binary_owner_only",
    "open_binary",
    "open_regular_binary_no_symlink",
    "open_regular_file_descriptor_no_symlink",
    "open_text",
    "read_regular_file_no_symlink",
)


def open_text(
    path: PathInput,
    *,
    mode: str = "r",
    encoding: str | None = "utf-8",
    errors: str | None = "strict",
    newline: str | None = None,
) -> io.TextIOBase:
    resolved = coerce_path(path)
    resolved_encoding = encoding or "utf-8"
    resolved_errors = errors or "strict"
    flags = _text_open_flags(mode)
    file_descriptor = os.open(resolved, flags, 0o666)
    file_handle = os.fdopen(
        file_descriptor,
        mode,
        encoding=resolved_encoding,
        errors=resolved_errors,
        newline=newline,
    )
    if not isinstance(file_handle, io.TextIOBase):
        raise TypeError("open_text() must return a text file handle.")
    return file_handle


@overload
def open_binary(
    path: PathInput,
    *,
    mode: Literal["rb", "wb", "ab", "xb"],
    buffering: Literal[0],
) -> io.FileIO: ...


@overload
def open_binary(
    path: PathInput,
    *,
    mode: Literal["rb"] = "rb",
    buffering: Literal[-1] = -1,
) -> io.BufferedReader: ...


@overload
def open_binary(
    path: PathInput,
    *,
    mode: Literal["wb", "ab", "xb"],
    buffering: Literal[-1] = -1,
) -> io.BufferedWriter: ...


def open_binary(
    path: PathInput,
    *,
    mode: str = "rb",
    buffering: int = -1,
) -> io.BufferedIOBase | io.RawIOBase:
    resolved = coerce_path(path)
    flags = _binary_open_flags(mode)
    file_descriptor = os.open(resolved, flags, 0o666)
    file_handle = os.fdopen(file_descriptor, mode, buffering=buffering)
    if not isinstance(file_handle, io.BufferedIOBase | io.RawIOBase):
        raise TypeError("open_binary() must return a binary file handle.")
    return file_handle


def create_binary_owner_only(path: PathInput) -> io.BufferedWriter:
    resolved = coerce_path(path)
    file_descriptor = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "posix":
            os.fchmod(file_descriptor, 0o600)
        file_handle = os.fdopen(file_descriptor, "wb")
    except OSError:
        os.close(file_descriptor)
        raise
    if not isinstance(file_handle, io.BufferedWriter):
        file_handle.close()
        raise TypeError("create_binary_owner_only() must return a binary writer.")
    return file_handle


def open_regular_file_descriptor_no_symlink(
    path: PathInput,
    *,
    writable: bool = False,
    not_found_message: str = "File source not found.",
    symlink_message: str = "File source must be a regular file, not a symlink.",
    open_message: str = "File source could not be opened.",
    inspect_message: str = "File source could not be inspected.",
    regular_file_message: str = "File source must be a regular file.",
) -> int:
    resolved = coerce_path(path)
    if os.path.islink(resolved):
        raise ValidationError(symlink_message)
    open_flags = secure_read_only_open_flags(directory=False) if os.name == "posix" else os.O_RDONLY
    if writable:
        open_flags |= os.O_RDWR
    try:
        file_descriptor = os.open(resolved, open_flags)
    except FileNotFoundError as exception:
        raise ValidationError(not_found_message) from exception
    except OSError as exception:
        if exception.errno == errno.ELOOP:
            raise ValidationError(symlink_message) from exception
        raise ValidationError(open_message) from exception
    try:
        file_status = os.fstat(file_descriptor)
    except OSError as exception:
        os.close(file_descriptor)
        raise ValidationError(inspect_message) from exception
    if not stat.S_ISREG(file_status.st_mode):
        os.close(file_descriptor)
        raise ValidationError(regular_file_message)
    return file_descriptor


def open_regular_binary_no_symlink(
    path: PathInput,
    *,
    not_found_message: str = "File source not found.",
    symlink_message: str = "File source must be a regular file, not a symlink.",
    open_message: str = "File source could not be opened.",
    inspect_message: str = "File source could not be inspected.",
    regular_file_message: str = "File source must be a regular file.",
) -> io.BufferedReader:
    file_descriptor = open_regular_file_descriptor_no_symlink(
        path,
        not_found_message=not_found_message,
        symlink_message=symlink_message,
        open_message=open_message,
        inspect_message=inspect_message,
        regular_file_message=regular_file_message,
    )
    try:
        file_handle = os.fdopen(file_descriptor, "rb")
    except OSError as exception:
        os.close(file_descriptor)
        raise ValidationError(open_message) from exception
    if not isinstance(file_handle, io.BufferedReader):
        file_handle.close()
        raise TypeError("open_regular_binary_no_symlink() must return a binary reader.")
    return file_handle


def read_regular_file_no_symlink(
    path: PathInput,
    *,
    max_bytes: int | None = None,
    not_found_message: str = "File source not found.",
    symlink_message: str = "File source must be a regular file, not a symlink.",
    open_message: str = "File source could not be opened.",
    inspect_message: str = "File source could not be inspected.",
    regular_file_message: str = "File source must be a regular file.",
) -> bytes:
    with open_regular_binary_no_symlink(
        path,
        not_found_message=not_found_message,
        symlink_message=symlink_message,
        open_message=open_message,
        inspect_message=inspect_message,
        regular_file_message=regular_file_message,
    ) as file_handle:
        if max_bytes is None:
            return file_handle.read()
        if max_bytes < 0:
            raise ValidationError("max_bytes must be non-negative.")
        return file_handle.read(max_bytes + 1)


def _text_open_flags(mode: str) -> int:
    if mode == "r":
        return os.O_RDONLY
    if mode == "w":
        return os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if mode == "a":
        return os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if mode == "x":
        return os.O_WRONLY | os.O_CREAT | os.O_EXCL
    raise ValueError(f"Unsupported text file mode: {mode}")


def _binary_open_flags(mode: str) -> int:
    if mode == "rb":
        return os.O_RDONLY
    if mode == "wb":
        return os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if mode == "ab":
        return os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if mode == "xb":
        return os.O_WRONLY | os.O_CREAT | os.O_EXCL
    raise ValueError(f"Unsupported binary file mode: {mode}")
