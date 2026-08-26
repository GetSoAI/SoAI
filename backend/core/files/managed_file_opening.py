"""SoAI - Managed file opening [backend/core/files/managed_file_opening.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.managed_storage_traversal import (
    close_file_descriptor_stack,
    normalize_storage_relative_path,
    open_storage_directory_stack,
    supports_storage_directory_descriptors,
)
from core.files.secure_open_flags import secure_read_only_open_flags
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = (
    "ManagedFileDescriptor",
    "open_managed_file_descriptor",
)


@dataclass(frozen=True, slots=True)
class ManagedFileDescriptor:
    descriptor: int
    size_bytes: int


def _open_regular_file_via_dir_fd(dir_fd: int, leaf: str) -> ManagedFileDescriptor:
    try:
        stat_before = os.stat(leaf, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError as exception:
        raise FileStorageSecurityError(f"Managed file '{leaf}' is missing.") from exception
    if stat.S_ISDIR(stat_before.st_mode):
        raise FileStorageSecurityError(f"Refusing to open directory '{leaf}'.")
    if stat.S_ISLNK(stat_before.st_mode):
        raise FileStorageSecurityError(f"Refusing to open symbolic link '{leaf}'.")
    if is_windows_reparse_point(stat_before):
        raise FileStorageSecurityError(f"Refusing to open reparse point '{leaf}'.")
    if not stat.S_ISREG(stat_before.st_mode):
        raise FileStorageSecurityError(f"Refusing to open non-regular file '{leaf}'.")
    try:
        descriptor = os.open(
            leaf,
            secure_read_only_open_flags(directory=False),
            dir_fd=dir_fd,
        )
    except OSError as exception:
        raise FileStorageSecurityError(f"Failed to open managed file '{leaf}'.") from exception
    completed = False
    try:
        try:
            stat_after = os.fstat(descriptor)
        except OSError as exception:
            raise FileStorageSecurityError(
                f"Failed to inspect opened managed file '{leaf}'.",
            ) from exception
        if stat_before.st_dev != stat_after.st_dev or stat_before.st_ino != stat_after.st_ino:
            raise FileStorageSecurityError(f"Managed file '{leaf}' was replaced during traversal.")
        if not stat.S_ISREG(stat_after.st_mode):
            raise FileStorageSecurityError(f"Managed file '{leaf}' is not regular.")
        if is_windows_reparse_point(stat_after):
            raise FileStorageSecurityError(f"Managed file '{leaf}' is a reparse point.")
        completed = True
        return ManagedFileDescriptor(descriptor=descriptor, size_bytes=int(stat_after.st_size))
    finally:
        if not completed:
            close_file_descriptor_stack([descriptor])


def open_managed_file_descriptor(storage_root: str, file_path: str) -> ManagedFileDescriptor:
    if os.name == "nt":
        with open_windows_managed_path_handles(
            storage_root,
            file_path,
            require_directory=False,
            read_leaf=True,
        ) as opened_path:
            descriptor = opened_path.detach_leaf_file_descriptor()
            return ManagedFileDescriptor(
                descriptor=descriptor,
                size_bytes=int(opened_path.stat_result.st_size),
            )
    parts = normalize_storage_relative_path(storage_root, file_path)
    if supports_storage_directory_descriptors():
        file_descriptor_stack = open_storage_directory_stack(
            storage_root,
            parts[:-1],
            missing_segment_returns_none=False,
        )
        if file_descriptor_stack is None:
            raise FileStorageSecurityError("Managed file storage path is missing.")
        try:
            return _open_regular_file_via_dir_fd(file_descriptor_stack[-1], parts[-1])
        finally:
            close_file_descriptor_stack(file_descriptor_stack)
    raise FileStorageSecurityError(
        "Managed file descriptors are unavailable on this platform.",
    )
