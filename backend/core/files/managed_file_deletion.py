"""SoAI - Managed file deletion [backend/core/files/managed_file_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import shutil
import stat

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.files.managed_storage_errors import FileDeletionSecurityError
from core.files.managed_storage_traversal import (
    close_file_descriptor_stack,
    normalize_storage_relative_path,
    open_storage_directory_stack,
    supports_storage_directory_descriptors,
)
from core.files.windows_readonly_deletion import (
    remove_file_with_readonly_support,
    remove_tree_with_readonly_support,
)
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = (
    "delete_managed_file",
    "delete_managed_path",
    "unlink_via_dir_fd",
    "unlink_via_path",
)


def unlink_via_dir_fd(dir_fd: int, leaf: str) -> bool:
    try:
        stat_info = os.stat(leaf, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if stat.S_ISDIR(stat_info.st_mode):
        raise FileDeletionSecurityError(f"Refusing to delete directory '{leaf}'.")
    if stat.S_ISLNK(stat_info.st_mode):
        raise FileDeletionSecurityError(f"Refusing to delete symbolic link '{leaf}'.")
    if is_windows_reparse_point(stat_info):
        raise FileDeletionSecurityError(f"Refusing to delete reparse point '{leaf}'.")
    os.unlink(leaf, dir_fd=dir_fd)
    return True


def _resolve_managed_target_via_path(
    storage_root: str,
    parts: list[str],
) -> str | None:
    current_path = storage_root
    for segment in parts[:-1]:
        current_path = os.path.join(current_path, segment)
        if not os.path.lexists(current_path):
            return None
        stat_info = os.lstat(current_path)
        if stat.S_ISLNK(stat_info.st_mode):
            raise FileDeletionSecurityError(
                f"Storage segment '{segment}' is a symbolic link. Aborting delete.",
            )
        if is_windows_reparse_point(stat_info):
            raise FileDeletionSecurityError(
                f"Storage segment '{segment}' is a reparse point. Aborting delete.",
            )
        if not stat.S_ISDIR(stat_info.st_mode):
            raise FileDeletionSecurityError(f"Storage segment '{segment}' is not a directory.")
    return os.path.join(current_path, parts[-1])


def unlink_via_path(storage_root: str, parts: list[str]) -> bool:
    target_path = _resolve_managed_target_via_path(storage_root, parts)
    if target_path is None:
        return False
    if not os.path.lexists(target_path):
        return False
    stat_info = os.lstat(target_path)
    if stat.S_ISDIR(stat_info.st_mode):
        raise FileDeletionSecurityError(f"Refusing to delete directory '{target_path}'.")
    if stat.S_ISLNK(stat_info.st_mode):
        raise FileDeletionSecurityError(f"Refusing to delete symbolic link '{target_path}'.")
    if is_windows_reparse_point(stat_info):
        raise FileDeletionSecurityError(f"Refusing to delete reparse point '{target_path}'.")
    os.unlink(target_path)
    return True


def _delete_path_via_dir_fd(dir_fd: int, leaf: str) -> bool:
    try:
        stat_info = os.stat(leaf, dir_fd=dir_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if stat.S_ISDIR(stat_info.st_mode) and not stat.S_ISLNK(stat_info.st_mode):
        if not bool(shutil.rmtree.avoids_symlink_attacks):
            raise FileDeletionSecurityError(
                "Secure recursive directory deletion is unavailable on this platform.",
            )
        shutil.rmtree(leaf, dir_fd=dir_fd)
        return True
    os.unlink(leaf, dir_fd=dir_fd)
    return True


def _delete_path_via_path(storage_root: str, parts: list[str]) -> bool:
    target_path = _resolve_managed_target_via_path(storage_root, parts)
    if target_path is None:
        return False
    try:
        stat_info = os.lstat(target_path)
    except FileNotFoundError:
        return False
    if is_windows_reparse_point(stat_info):
        if stat.S_ISDIR(stat_info.st_mode) and not stat.S_ISLNK(stat_info.st_mode):
            os.rmdir(target_path)
        else:
            os.unlink(target_path)
        return True
    if stat.S_ISDIR(stat_info.st_mode) and not stat.S_ISLNK(stat_info.st_mode):
        remove_tree_with_readonly_support(target_path)
        return True
    remove_file_with_readonly_support(target_path)
    return True


def _delete_normalized_managed_entry(
    storage_root: str,
    parts: list[str],
    *,
    allow_directory: bool,
) -> bool:
    if supports_storage_directory_descriptors():
        descriptor_stack = open_storage_directory_stack(
            storage_root,
            parts[:-1],
            missing_segment_returns_none=True,
        )
        if descriptor_stack is None:
            return False
        try:
            if allow_directory:
                return _delete_path_via_dir_fd(descriptor_stack[-1], parts[-1])
            return unlink_via_dir_fd(descriptor_stack[-1], parts[-1])
        finally:
            close_file_descriptor_stack(descriptor_stack)
    if allow_directory:
        return _delete_path_via_path(storage_root, parts)
    return unlink_via_path(storage_root, parts)


async def delete_managed_path(storage_root: str, path: str) -> bool:
    parts = normalize_storage_relative_path(storage_root, path)
    try:
        return await uncancel_and_wait(
            asyncio.to_thread(
                _delete_normalized_managed_entry,
                storage_root,
                parts,
                allow_directory=True,
            ),
        )
    except FileNotFoundError:
        return False
    except OSError as exception:
        raise FileDeletionSecurityError(
            f"Failed to remove managed path '{path}'.",
        ) from exception


async def delete_managed_file(storage_root: str, file_path: str) -> bool:
    parts = normalize_storage_relative_path(storage_root, file_path)
    try:
        return await uncancel_and_wait(
            asyncio.to_thread(
                _delete_normalized_managed_entry,
                storage_root,
                parts,
                allow_directory=False,
            ),
        )
    except FileNotFoundError:
        return False
    except OSError as exception:
        raise FileDeletionSecurityError(
            f"Failed to remove '{file_path}': {exception}",
        ) from exception
