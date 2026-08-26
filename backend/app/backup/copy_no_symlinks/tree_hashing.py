"""SoAI - Secure directory hashing (no symlinks) [backend/app/backup/copy_no_symlinks/tree_hashing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os

from app.backup.copy_no_symlinks.deadlines import check_deadline
from app.backup.copy_no_symlinks.file_copy import sync_copy_file_and_hash_no_symlinks
from app.backup.copy_no_symlinks.tree_hash_format import (
    update_tree_hasher_for_relative_directory,
    update_tree_hasher_for_relative_file,
)
from core.errors.exceptions import ValidationError
from files.archive import sync_raise_if_symlink

__all__ = ("sync_hash_directory_no_symlinks",)


def sync_hash_directory_no_symlinks(
    source_root: str,
    *,
    deadline_monotonic: float | None = None,
) -> tuple[int, str]:
    if not source_root.strip():
        raise ValidationError("source_root is required.")
    sync_raise_if_symlink(source_root, context="tree hash source")
    if not os.path.isdir(source_root):
        raise ValidationError(f"Expected a directory at {source_root}.")

    dir_hasher = hashlib.sha256()
    total_bytes = 0

    for root, dir_names, file_names in os.walk(source_root, topdown=True, followlinks=False):
        check_deadline(deadline_monotonic, context=f"hash_dir:{root}")
        dir_names.sort()
        file_names.sort()
        relative_root = os.path.relpath(root, source_root)
        if relative_root == ".":
            relative_root = ""
        if relative_root:
            update_tree_hasher_for_relative_directory(dir_hasher, relative_root)
        for directory_name in dir_names:
            directory_path = os.path.join(root, directory_name)
            sync_raise_if_symlink(directory_path, context="tree hash entry")
        for file_name in file_names:
            source_file = os.path.join(root, file_name)
            relative_file = os.path.relpath(source_file, source_root)
            check_deadline(deadline_monotonic, context=f"hash_dir_file:{source_file}")
            file_size, file_hash = sync_copy_file_and_hash_no_symlinks(
                source_file,
                None,
                deadline_monotonic=deadline_monotonic,
            )
            update_tree_hasher_for_relative_file(dir_hasher, relative_file, file_hash)
            total_bytes += file_size

    return total_bytes, dir_hasher.hexdigest()
