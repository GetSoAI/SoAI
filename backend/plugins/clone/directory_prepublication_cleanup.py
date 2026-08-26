"""SoAI - Prepublication clone directory cleanup [backend/plugins/clone/directory_prepublication_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.directory_artifact_identity import (
    read_directory_identity_entry,
)
from plugins.clone.directory_publication_ownership import PublishedDirectoryEntry
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.file_artifact_removal import remove_file_artifact_atomically
from plugins.clone.ownership_marker import (
    DIRECTORY_IDENTITY,
    OwnershipMarker,
    replace_ownership_marker,
)
from plugins.clone.ownership_marker_builders import (
    build_directory_claim_marker,
    build_published_file_marker,
)

__all__ = (
    "is_uninitialized_directory_claim",
    "recover_uninitialized_directory_claim",
    "remove_empty_staging_tree",
    "restore_published_entries",
    "require_valid_unclaimed_directory_skeleton",
)


def _require_published_entry_identity(
    path: str,
    entry: PublishedDirectoryEntry,
) -> None:
    identity = read_file_artifact_identity(path)
    if not file_artifact_identity_matches(
        identity,
        device=entry.device,
        inode=entry.inode,
        size_bytes=entry.size_bytes,
        sha256_hex=entry.sha256_hex,
    ):
        raise StateError("Clone published file ownership identity mismatch.")


def _restore_published_file(entry: PublishedDirectoryEntry, task_id: str) -> None:
    marker = build_published_file_marker(
        task_id,
        device=entry.device,
        inode=entry.inode,
        size_bytes=entry.size_bytes,
        sha256_hex=entry.sha256_hex,
    )
    if os.path.lexists(entry.source_path):
        _require_published_entry_identity(entry.source_path, entry)
        if os.path.lexists(entry.final_path):
            remove_file_artifact_atomically(entry.final_path, marker, None)
        return
    if not os.path.lexists(entry.final_path):
        raise StateError("Clone published file is missing during staging restoration.")
    _require_published_entry_identity(entry.final_path, entry)
    try:
        os.link(entry.final_path, entry.source_path, follow_symlinks=False)
    except FileExistsError:
        _require_published_entry_identity(entry.source_path, entry)
    fsync_directory(os.path.dirname(entry.source_path), strict=True)
    _require_published_entry_identity(entry.source_path, entry)
    remove_file_artifact_atomically(entry.final_path, marker, None)


def restore_published_entries(
    entries: list[PublishedDirectoryEntry],
    task_id: str,
) -> None:
    for entry in entries:
        if not entry.is_directory:
            continue
        os.makedirs(entry.source_path, exist_ok=True)
        source_stat = os.lstat(entry.source_path)
        if not stat.S_ISDIR(source_stat.st_mode) or stat.S_ISLNK(source_stat.st_mode):
            raise StateError("Clone staging directory changed during publication cleanup.")
    for entry in reversed(entries):
        if not entry.is_directory:
            _restore_published_file(entry, task_id)


def is_uninitialized_directory_claim(marker: OwnershipMarker) -> bool:
    return (
        marker.state == "claim"
        and marker.device == -1
        and marker.inode == -1
        and marker.size_bytes is None
        and marker.sha256_hex is None
        and not marker.entries
    )


def require_valid_unclaimed_directory_skeleton(
    final_path: str,
    staging_path: str,
    marker: OwnershipMarker,
) -> None:
    if marker.state != "claim":
        return
    for entry in marker.entries:
        if entry.entry_type != "directory" or entry.device != -1 or entry.inode != -1:
            continue
        entry_parts = entry.relative_path.split("/")
        final_entry_path = os.path.join(final_path, *entry_parts)
        if not os.path.lexists(final_entry_path):
            continue
        staged_entry_path = os.path.join(staging_path, *entry_parts)
        try:
            staged_entry_stat = os.lstat(staged_entry_path)
        except FileNotFoundError as exception:
            raise StateError("Clone directory staging identity is missing.") from exception
        if not stat.S_ISDIR(staged_entry_stat.st_mode) or stat.S_ISLNK(staged_entry_stat.st_mode):
            raise StateError("Clone directory staging identity is invalid.")
        final_entry_stat = os.lstat(final_entry_path)
        if not stat.S_ISDIR(final_entry_stat.st_mode) or stat.S_ISLNK(final_entry_stat.st_mode):
            raise StateError("Clone directory skeleton ownership identity is invalid.")


def remove_empty_staging_tree(
    staging_path: str,
    published_entries: list[PublishedDirectoryEntry],
) -> None:
    for entry in reversed(published_entries):
        if entry.is_directory:
            os.rmdir(entry.source_path)
    os.rmdir(staging_path)
    fsync_directory(os.path.dirname(staging_path), strict=True)


def recover_uninitialized_directory_claim(
    final_path: str,
    marker_path: str,
    marker_staging_path: str | None,
    task_id: str,
) -> OwnershipMarker | None:
    try:
        root_stat = os.lstat(final_path)
    except FileNotFoundError:
        if marker_staging_path is not None:
            os.unlink(marker_staging_path)
        os.unlink(marker_path)
        fsync_directory(os.path.dirname(final_path), strict=True)
        return None
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        raise StateError("Clone directory prepublication root was replaced.")
    names = set(os.listdir(final_path))
    if not names:
        try:
            os.rmdir(final_path)
        except OSError as exception:
            raise StateError(
                "Clone directory contains foreign entries after owned cleanup."
            ) from exception
        if marker_staging_path is not None:
            os.unlink(marker_staging_path)
        os.unlink(marker_path)
        fsync_directory(os.path.dirname(final_path), strict=True)
        return None
    if names != {DIRECTORY_IDENTITY}:
        raise StateError("Clone directory contains foreign entries after owned cleanup.")
    identity_entry = read_directory_identity_entry(
        os.path.join(final_path, DIRECTORY_IDENTITY),
        task_id,
    )
    promoted = build_directory_claim_marker(
        task_id,
        device=root_stat.st_dev,
        inode=root_stat.st_ino,
        entries=(identity_entry,),
    )
    replace_ownership_marker(marker_path, promoted)
    if marker_staging_path is not None and os.path.lexists(marker_staging_path):
        os.unlink(marker_staging_path)
    return promoted
