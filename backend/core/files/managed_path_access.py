"""SoAI - Race-resistant managed path inspection and directory access [backend/core/files/managed_path_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from collections.abc import Generator
from contextlib import contextmanager

from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.managed_storage_traversal import (
    close_file_descriptor_stack,
    normalize_storage_relative_path,
    open_directory_fd,
    open_storage_directory_stack,
    supports_storage_directory_descriptors,
)
from core.files.path_policy import is_same_path
from core.files.secure_open_flags import secure_read_only_open_flags
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = (
    "open_managed_directory_descriptor",
    "supports_managed_directory_descriptors",
    "stat_managed_path",
)


def supports_managed_directory_descriptors() -> bool:
    return supports_storage_directory_descriptors() and os.listdir in os.supports_fd


def stat_managed_path(storage_root: str, entry_path: str) -> os.stat_result:
    if os.name == "nt":
        with open_windows_managed_path_handles(
            storage_root,
            entry_path,
            require_directory=None,
        ) as opened_path:
            return opened_path.stat_result
    if not supports_managed_directory_descriptors():
        raise FileStorageSecurityError(
            "Managed path descriptors are unavailable on this platform.",
        )
    if is_same_path(storage_root, entry_path):
        with open_managed_directory_descriptor(storage_root, entry_path) as descriptor:
            return os.fstat(descriptor)
    parts = normalize_storage_relative_path(storage_root, entry_path)
    descriptor_stack = open_storage_directory_stack(
        storage_root,
        parts[:-1],
        missing_segment_returns_none=False,
    )
    if descriptor_stack is None:
        raise FileStorageSecurityError("Managed path is missing.")
    try:
        try:
            entry_status = os.stat(
                parts[-1],
                dir_fd=descriptor_stack[-1],
                follow_symlinks=False,
            )
        except FileNotFoundError as exception:
            raise FileStorageSecurityError("Managed path is missing.") from exception
        if stat.S_ISLNK(entry_status.st_mode):
            raise FileStorageSecurityError("Managed path is a symbolic link.")
        if is_windows_reparse_point(entry_status):
            raise FileStorageSecurityError("Managed path is a reparse point.")
        return entry_status
    finally:
        close_file_descriptor_stack(descriptor_stack)


@contextmanager
def open_managed_directory_descriptor(
    storage_root: str,
    directory_path: str,
) -> Generator[int]:
    if not supports_managed_directory_descriptors():
        raise FileStorageSecurityError(
            "Managed directory descriptors are unavailable on this platform.",
        )
    descriptor_stack: list[int]
    if is_same_path(storage_root, directory_path):
        descriptor_stack = [
            open_directory_fd(
                None,
                storage_root,
                flags=secure_read_only_open_flags(directory=True),
            ),
        ]
    else:
        parts = normalize_storage_relative_path(storage_root, directory_path)
        opened_stack = open_storage_directory_stack(
            storage_root,
            parts,
            missing_segment_returns_none=False,
        )
        if opened_stack is None:
            raise FileStorageSecurityError("Managed directory is missing.")
        descriptor_stack = opened_stack
    try:
        directory_status = os.fstat(descriptor_stack[-1])
        if not stat.S_ISDIR(directory_status.st_mode):
            raise FileStorageSecurityError("Managed path is not a directory.")
        if is_windows_reparse_point(directory_status):
            raise FileStorageSecurityError("Managed directory is a reparse point.")
        yield descriptor_stack[-1]
    finally:
        close_file_descriptor_stack(descriptor_stack)
