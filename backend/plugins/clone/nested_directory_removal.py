"""SoAI - Atomic owned nested directory removal [backend/plugins/clone/nested_directory_removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.file_artifact_removal import remove_file_artifact_atomically
from plugins.clone.ownership_marker import DIRECTORY_IDENTITY, OwnershipEntry, OwnershipMarker

__all__ = (
    "remove_owned_nested_directory",
    "remove_preclaimed_empty_directory",
)


def remove_preclaimed_empty_directory(path: str) -> None:
    try:
        path_stat = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(path_stat.st_mode) or stat.S_ISLNK(path_stat.st_mode):
        raise StateError("Clone directory skeleton ownership identity is invalid.")
    try:
        os.rmdir(path)
    except OSError as exception:
        raise StateError(
            "Clone directory contains foreign entries after owned cleanup."
        ) from exception
    fsync_directory(os.path.dirname(path), strict=True)


def _require_owned_directory(
    path: str,
    directory_entry: OwnershipEntry,
    identity_entry: OwnershipEntry,
) -> None:
    path_stat = os.lstat(path)
    if (
        not stat.S_ISDIR(path_stat.st_mode)
        or stat.S_ISLNK(path_stat.st_mode)
        or path_stat.st_dev != directory_entry.device
        or path_stat.st_ino != directory_entry.inode
        or set(os.listdir(path)) != {DIRECTORY_IDENTITY}
    ):
        raise StateError("Clone nested directory ownership identity mismatch.")
    identity = read_file_artifact_identity(os.path.join(path, DIRECTORY_IDENTITY))
    if not file_artifact_identity_matches(
        identity,
        device=identity_entry.device,
        inode=identity_entry.inode,
        size_bytes=identity_entry.size_bytes,
        sha256_hex=identity_entry.sha256_hex,
    ):
        raise StateError("Clone nested directory identity file mismatch.")


def remove_owned_nested_directory(
    path: str,
    task_id: str,
    directory_entry: OwnershipEntry,
    identity_entry: OwnershipEntry,
) -> None:
    capture_path = f"{path}.soai-clone-removal-{task_id}"
    if os.path.lexists(capture_path):
        if os.path.lexists(path):
            raise StateError("Clone nested directory removal detected a foreign replacement.")
        _require_owned_directory(capture_path, directory_entry, identity_entry)
    elif os.path.lexists(path):
        _require_owned_directory(path, directory_entry, identity_entry)
        os.rename(path, capture_path)
        fsync_directory(os.path.dirname(path), strict=True)
        _require_owned_directory(capture_path, directory_entry, identity_entry)
    else:
        return
    remove_file_artifact_atomically(
        os.path.join(capture_path, DIRECTORY_IDENTITY),
        OwnershipMarker(
            owner=task_id,
            artifact_type="file",
            state="published",
            device=identity_entry.device,
            inode=identity_entry.inode,
            size_bytes=identity_entry.size_bytes,
            sha256_hex=identity_entry.sha256_hex,
        ),
        None,
    )
    if os.listdir(capture_path):
        raise StateError("Clone nested directory removal contains foreign entries.")
    try:
        os.rmdir(capture_path)
    except OSError as exception:
        raise StateError("Clone nested directory could not be removed atomically.") from exception
    fsync_directory(os.path.dirname(path), strict=True)
