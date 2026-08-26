"""SoAI - Archive file utilities [backend/files/archive.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import posixpath
import tarfile

from core.errors.exceptions import SecurityError, ValidationError

__all__ = (
    "sync_calculate_backup_export_archive_max_size",
    "sync_raise_if_symlink",
    "sync_write_backup_export_archive",
)

TAR_BLOCK_SIZE = 512
TAR_END_BLOCK_BYTES = TAR_BLOCK_SIZE * 2
TAR_PAX_HEADER_ALLOWANCE_BYTES = TAR_BLOCK_SIZE * 8
GZIP_FIXED_OVERHEAD_BYTES = 4096
GZIP_EXPANSION_DIVISOR = 128


def sync_raise_if_symlink(path: str, *, context: str) -> None:
    if not path.strip():
        raise ValidationError("path is required.")
    if not context.strip():
        raise ValidationError("context is required.")
    if os.path.islink(path):
        raise SecurityError(f"Symlinks are not allowed for {context}: {path}")


def sync_calculate_backup_export_archive_max_size(backup_path: str, backup_id: str) -> int:
    if not backup_path.strip():
        raise ValidationError("backup_path is required.")
    if not backup_id.strip():
        raise ValidationError("backup_id is required.")

    sync_raise_if_symlink(backup_path, context="backup export source")

    tar_bytes = _tar_member_upper_bound(0)
    for root, dir_names, file_names in os.walk(backup_path, topdown=True, followlinks=False):
        dir_names.sort()
        file_names.sort()
        for directory_name in dir_names:
            directory_path = os.path.join(root, directory_name)
            sync_raise_if_symlink(directory_path, context="backup export directory")
            tar_bytes += _tar_member_upper_bound(0)
        for file_name in file_names:
            file_path = os.path.join(root, file_name)
            sync_raise_if_symlink(file_path, context="backup export file")
            tar_bytes += _tar_member_upper_bound(os.path.getsize(file_path))
    tar_bytes += TAR_END_BLOCK_BYTES
    return tar_bytes + GZIP_FIXED_OVERHEAD_BYTES + max(1, tar_bytes // GZIP_EXPANSION_DIVISOR)


def sync_write_backup_export_archive(backup_path: str, archive_path: str, backup_id: str) -> None:
    if not backup_path.strip():
        raise ValidationError("backup_path is required.")
    if not archive_path.strip():
        raise ValidationError("archive_path is required.")
    if not backup_id.strip():
        raise ValidationError("backup_id is required.")

    sync_raise_if_symlink(backup_path, context="backup export source")

    with tarfile.open(archive_path, "w:gz") as tar_archive:
        tar_archive.add(backup_path, arcname=backup_id, recursive=False)
        for root, dir_names, file_names in os.walk(backup_path, topdown=True, followlinks=False):
            dir_names.sort()
            file_names.sort()
            rel_root = os.path.relpath(root, backup_path)
            if rel_root == ".":
                archive_root = backup_id
            else:
                rel_root_posix = rel_root.replace("\\", "/")
                archive_root = posixpath.join(backup_id, rel_root_posix)
            for directory_name in dir_names:
                directory_path = os.path.join(root, directory_name)
                sync_raise_if_symlink(directory_path, context="backup export directory")
                tar_archive.add(
                    directory_path,
                    arcname=posixpath.join(archive_root, directory_name),
                    recursive=False,
                )
            for file_name in file_names:
                file_path = os.path.join(root, file_name)
                sync_raise_if_symlink(file_path, context="backup export file")
                tar_archive.add(
                    file_path,
                    arcname=posixpath.join(archive_root, file_name),
                    recursive=False,
                )


def _tar_member_upper_bound(size_bytes: int) -> int:
    data_blocks = (max(0, size_bytes) + TAR_BLOCK_SIZE - 1) // TAR_BLOCK_SIZE
    return TAR_BLOCK_SIZE + TAR_PAX_HEADER_ALLOWANCE_BYTES + (data_blocks * TAR_BLOCK_SIZE)
