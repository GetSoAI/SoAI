"""SoAI - Secure directory copy helpers (no symlinks) [backend/app/backup/copy_no_symlinks/tree_copy.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.backup.copy_no_symlinks.deadlines import check_deadline
from app.backup.copy_no_symlinks.file_copy import (
    sync_copy_file_and_hash_no_symlinks,
    sync_copy_file_no_symlinks,
)
from app.backup.copy_no_symlinks.tree_hash_format import (
    update_tree_hasher_for_relative_directory,
    update_tree_hasher_for_relative_file,
)
from core.errors.exceptions import ValidationError
from core.filesystem.atomic_write_primitives import fsync_directory
from files.archive import sync_raise_if_symlink

if TYPE_CHECKING:
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

    type IgnoreFunc = Callable[[str, list[str]], set[str]]

__all__ = (
    "sync_copy_directory_and_hash_no_symlinks",
    "sync_copy_tree_no_symlinks",
    "sync_fsync_directory_tree",
)


def sync_fsync_directory_tree(root_path: str) -> None:
    if not isinstance(root_path, str) or not root_path.strip():
        raise ValidationError("root_path is required.")
    sync_raise_if_symlink(root_path, context="directory durability root")
    if not os.path.isdir(root_path):
        raise ValidationError(f"Expected a directory at {root_path}.")
    for current_root, directory_names, file_names in os.walk(
        root_path,
        topdown=False,
        followlinks=False,
    ):
        for directory_name in directory_names:
            sync_raise_if_symlink(
                os.path.join(current_root, directory_name),
                context="directory durability entry",
            )
        for file_name in file_names:
            sync_raise_if_symlink(
                os.path.join(current_root, file_name),
                context="directory durability entry",
            )
        fsync_directory(current_root, strict=True)


def _prepare_copy_tree_roots(source_root: str, destination_root: str) -> None:
    if not isinstance(source_root, str) or not source_root.strip():
        raise ValidationError("source_root is required.")
    if not isinstance(destination_root, str) or not destination_root.strip():
        raise ValidationError("destination_root is required.")
    sync_raise_if_symlink(source_root, context="tree copy source")
    if not os.path.isdir(source_root):
        raise ValidationError(f"Expected a directory at {source_root}.")
    if os.path.exists(destination_root):
        raise ValidationError(f"Destination already exists: {destination_root}")
    os.makedirs(destination_root, mode=0o700, exist_ok=False)


def _prepare_copy_tree_roots_allow_existing_empty_destination(
    source_root: str,
    destination_root: str,
) -> None:
    if not isinstance(source_root, str) or not source_root.strip():
        raise ValidationError("source_root is required.")
    if not isinstance(destination_root, str) or not destination_root.strip():
        raise ValidationError("destination_root is required.")
    sync_raise_if_symlink(source_root, context="tree copy source")
    if not os.path.isdir(source_root):
        raise ValidationError(f"Expected a directory at {source_root}.")
    if os.path.lexists(destination_root) and os.path.islink(destination_root):
        raise ValidationError(f"Destination must not be a symlink: {destination_root}")
    if not os.path.exists(destination_root):
        os.makedirs(destination_root, mode=0o700, exist_ok=False)
        return
    if not os.path.isdir(destination_root):
        raise ValidationError(f"Destination must be a directory: {destination_root}")
    if os.listdir(destination_root):
        raise ValidationError(f"Destination directory must be empty: {destination_root}")


def sync_copy_directory_and_hash_no_symlinks(
    source_root: str,
    destination_root: str,
    *,
    deadline_monotonic: float | None = None,
    allow_existing_empty_destination: bool = False,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> tuple[int, str]:
    if allow_existing_empty_destination:
        _prepare_copy_tree_roots_allow_existing_empty_destination(source_root, destination_root)
    else:
        _prepare_copy_tree_roots(source_root, destination_root)

    dir_hasher = hashlib.sha256()
    total_bytes = 0
    for root, dir_names, file_names in os.walk(source_root, topdown=True, followlinks=False):
        check_deadline(deadline_monotonic, context=f"copy_dir:{root}")
        dir_names.sort()
        file_names.sort()
        relative_root = os.path.relpath(root, source_root)
        if relative_root == ".":
            relative_root = ""
        if relative_root:
            os.makedirs(
                os.path.join(destination_root, relative_root),
                mode=0o700,
                exist_ok=True,
            )
            update_tree_hasher_for_relative_directory(dir_hasher, relative_root)
        for directory_name in dir_names:
            directory_path = os.path.join(root, directory_name)
            sync_raise_if_symlink(directory_path, context="tree copy entry")
            relative_dir = os.path.relpath(directory_path, source_root)
            os.makedirs(
                os.path.join(destination_root, relative_dir),
                mode=0o700,
                exist_ok=True,
            )
        for file_name in file_names:
            source_file = os.path.join(root, file_name)
            relative_file = os.path.relpath(source_file, source_root)
            destination_file = os.path.join(destination_root, relative_file)
            check_deadline(deadline_monotonic, context=f"copy_dir_file:{source_file}")
            file_size, file_hash = sync_copy_file_and_hash_no_symlinks(
                source_file,
                destination_file,
                deadline_monotonic=deadline_monotonic,
                write_reservation=write_reservation,
            )
            update_tree_hasher_for_relative_file(dir_hasher, relative_file, file_hash)
            total_bytes += file_size

    return total_bytes, dir_hasher.hexdigest()


def sync_copy_tree_no_symlinks(
    source_root: str,
    destination_root: str,
    *,
    ignore: IgnoreFunc | None = None,
    deadline_monotonic: float | None = None,
    allow_existing_empty_destination: bool = False,
    write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
) -> None:
    if allow_existing_empty_destination:
        _prepare_copy_tree_roots_allow_existing_empty_destination(source_root, destination_root)
    else:
        _prepare_copy_tree_roots(source_root, destination_root)

    for root, dir_names, file_names in os.walk(source_root, topdown=True, followlinks=False):
        ignore_names: set[str] = set()
        if ignore is not None:
            ignore_names = set(ignore(root, dir_names + file_names) or [])

        check_deadline(deadline_monotonic, context=f"copy_tree:{root}")
        dir_names[:] = [
            directory_name for directory_name in dir_names if directory_name not in ignore_names
        ]
        dir_names.sort()
        file_names.sort()

        for directory_name in dir_names:
            directory_path = os.path.join(root, directory_name)
            sync_raise_if_symlink(directory_path, context="tree copy entry")
            relative_dir = os.path.relpath(directory_path, source_root)
            os.makedirs(
                os.path.join(destination_root, relative_dir),
                mode=0o700,
                exist_ok=True,
            )

        for file_name in file_names:
            if file_name in ignore_names:
                continue
            source_file = os.path.join(root, file_name)
            relative_file = os.path.relpath(source_file, source_root)
            destination_file = os.path.join(destination_root, relative_file)
            check_deadline(deadline_monotonic, context=f"copy_tree_file:{source_file}")
            sync_copy_file_no_symlinks(
                source_file,
                destination_file,
                deadline_monotonic=deadline_monotonic,
                write_reservation=write_reservation,
            )
