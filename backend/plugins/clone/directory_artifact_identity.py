"""SoAI - Exact clone directory identity verification [backend/plugins/clone/directory_artifact_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.atomic_writes import atomic_create_text_content_exclusive
from core.filesystem.open_files import open_regular_binary_no_symlink
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.ownership_marker import (
    DIRECTORY_IDENTITY,
    OwnershipEntry,
    OwnershipMarker,
)

__all__ = (
    "create_directory_identity",
    "directory_artifact_identity_matches",
    "read_directory_identity_entry",
)


def create_directory_identity(final_path: str, task_id: str) -> OwnershipEntry:
    identity_path = os.path.join(final_path, DIRECTORY_IDENTITY)
    atomic_create_text_content_exclusive(
        identity_path,
        task_id,
        encoding="ascii",
        ensure_parent=False,
        file_mode=0o600,
    )
    identity = read_file_artifact_identity(identity_path)
    return OwnershipEntry(
        relative_path=DIRECTORY_IDENTITY,
        entry_type="file",
        device=identity.device,
        inode=identity.inode,
        size_bytes=identity.size_bytes,
        sha256_hex=identity.sha256_hex,
    )


def _read_identity_content(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while remaining > 0:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_directory_identity_entry(
    identity_path: str,
    task_id: str,
) -> OwnershipEntry:
    first_identity = read_file_artifact_identity(identity_path)
    try:
        with open_regular_binary_no_symlink(
            identity_path,
            not_found_message="Clone directory identity is unavailable.",
            symlink_message="Clone directory identity is unavailable.",
            open_message="Clone directory identity is unavailable.",
            inspect_message="Clone directory identity is unavailable.",
            regular_file_message="Clone directory identity is unavailable.",
        ) as file_handle:
            descriptor = file_handle.fileno()
            descriptor_stat = os.fstat(descriptor)
            if (
                descriptor_stat.st_dev != first_identity.device
                or descriptor_stat.st_ino != first_identity.inode
            ):
                raise StateError("Clone directory identity changed during open.")
            content = _read_identity_content(descriptor, len(task_id) + 1)
    except ValidationError as exception:
        raise StateError(str(exception)) from exception
    except OSError as exception:
        raise StateError("Clone directory identity is unavailable.") from exception
    second_identity = read_file_artifact_identity(identity_path)
    if first_identity != second_identity or content != task_id.encode("ascii"):
        raise StateError("Clone directory identity owner is invalid.")
    return OwnershipEntry(
        relative_path=DIRECTORY_IDENTITY,
        entry_type="file",
        device=second_identity.device,
        inode=second_identity.inode,
        size_bytes=second_identity.size_bytes,
        sha256_hex=second_identity.sha256_hex,
    )


def directory_artifact_identity_matches(final_path: str, marker: OwnershipMarker) -> bool:
    try:
        root_stat = os.lstat(final_path)
    except FileNotFoundError:
        return False
    if (
        marker.artifact_type != "directory"
        or not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_dev != marker.device
        or root_stat.st_ino != marker.inode
    ):
        return False
    identity_entries = tuple(
        entry for entry in marker.entries if entry.relative_path == DIRECTORY_IDENTITY
    )
    if len(identity_entries) != 1:
        return False
    identity_entry = identity_entries[0]
    if identity_entry.entry_type != "file":
        return False
    try:
        identity = read_file_artifact_identity(os.path.join(final_path, DIRECTORY_IDENTITY))
    except StateError:
        return False
    return file_artifact_identity_matches(
        identity,
        device=identity_entry.device,
        inode=identity_entry.inode,
        size_bytes=identity_entry.size_bytes,
        sha256_hex=identity_entry.sha256_hex,
    )
