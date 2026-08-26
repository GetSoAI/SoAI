"""SoAI - Clone staging artifact ownership [backend/plugins/clone/staging_artifact_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import stat

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.directory_prepublication_cleanup import (
    is_uninitialized_directory_claim,
)
from plugins.clone.directory_publication_ownership import (
    build_directory_ownership_entries,
)
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.file_artifact_removal import (
    remove_file_artifact_atomically,
    remove_owned_file_entry_atomically,
)
from plugins.clone.ownership_marker import (
    OwnershipEntry,
    OwnershipMarker,
    artifact_ownership_marker_path,
    ownership_marker_staging_path,
    replace_ownership_marker,
    require_ownership_marker,
    write_ownership_marker,
)
from plugins.clone.ownership_marker_builders import (
    build_published_directory_marker,
    build_published_file_marker,
)

__all__ = (
    "claim_staging_artifact_ownership",
    "record_staging_artifact_ownership",
    "release_staging_artifact_ownership",
    "remove_owned_staging_artifact",
    "require_staging_artifact_ownership",
)


def claim_staging_artifact_ownership(
    staging_path: str,
    task_id: str,
    artifact_type: str,
) -> None:
    if artifact_type not in {"directory", "file"}:
        raise StateError("Clone staging artifact type is invalid.")
    if os.path.lexists(staging_path):
        raise StateError("Clone staging path already exists.")
    write_ownership_marker(
        artifact_ownership_marker_path(staging_path),
        OwnershipMarker(
            owner=task_id,
            artifact_type=artifact_type,
            state="claim",
            device=-1,
            inode=-1,
            size_bytes=None,
            sha256_hex=None,
        ),
    )


def record_staging_artifact_ownership(
    staging_path: str,
    task_id: str,
    artifact_type: str,
) -> None:
    marker_path = artifact_ownership_marker_path(staging_path)
    claim = require_ownership_marker(
        marker_path,
        task_id,
        artifact_type,
        require_published=False,
    )
    if claim.state != "claim":
        raise StateError("Clone staging artifact ownership is already recorded.")
    if artifact_type == "file":
        identity = read_file_artifact_identity(staging_path)
        marker = build_published_file_marker(
            task_id,
            device=identity.device,
            inode=identity.inode,
            size_bytes=identity.size_bytes,
            sha256_hex=identity.sha256_hex,
        )
    elif artifact_type == "directory":
        root_stat = os.lstat(staging_path)
        if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
            raise StateError("Clone directory staging ownership identity is invalid.")
        marker = build_published_directory_marker(
            task_id,
            device=root_stat.st_dev,
            inode=root_stat.st_ino,
            entries=build_directory_ownership_entries(staging_path),
        )
    else:
        raise StateError("Clone staging artifact type is invalid.")
    replace_ownership_marker(marker_path, marker)


def require_staging_artifact_ownership(
    staging_path: str,
    task_id: str,
    artifact_type: str,
) -> OwnershipMarker:
    marker = require_ownership_marker(
        artifact_ownership_marker_path(staging_path),
        task_id,
        artifact_type,
        require_published=True,
    )
    if artifact_type == "file":
        identity = read_file_artifact_identity(staging_path)
        if not file_artifact_identity_matches(
            identity,
            device=marker.device,
            inode=marker.inode,
            size_bytes=marker.size_bytes,
            sha256_hex=marker.sha256_hex,
        ):
            raise StateError("Clone file staging ownership identity is invalid.")
        return marker
    if artifact_type != "directory":
        raise StateError("Clone staging artifact type is invalid.")
    root_stat = os.lstat(staging_path)
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or root_stat.st_dev != marker.device
        or root_stat.st_ino != marker.inode
    ):
        raise StateError("Clone directory staging ownership identity is invalid.")
    return marker


def _remove_staging_file(
    path: str,
    task_id: str,
    entry: OwnershipEntry,
) -> None:
    if not os.path.lexists(path):
        return
    remove_owned_file_entry_atomically(path, task_id, entry)


def _remove_staging_directory_entries(
    staging_path: str,
    marker: OwnershipMarker,
) -> None:
    root_stat = os.lstat(staging_path)
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or root_stat.st_dev != marker.device
        or root_stat.st_ino != marker.inode
    ):
        raise StateError("Clone directory staging ownership identity is invalid.")
    for entry in reversed(marker.entries):
        entry_path = os.path.join(staging_path, *entry.relative_path.split("/"))
        if entry.entry_type == "file":
            _remove_staging_file(entry_path, marker.owner, entry)
            continue
        try:
            entry_stat = os.lstat(entry_path)
        except FileNotFoundError:
            continue
        if (
            not stat.S_ISDIR(entry_stat.st_mode)
            or stat.S_ISLNK(entry_stat.st_mode)
            or entry_stat.st_dev != entry.device
            or entry_stat.st_ino != entry.inode
        ):
            raise StateError("Clone directory staging ownership identity is invalid.")
        try:
            os.rmdir(entry_path)
        except OSError as exception:
            raise StateError("Clone directory staging contains foreign entries.") from exception
    if os.listdir(staging_path):
        raise StateError("Clone directory staging contains foreign entries.")
    os.rmdir(staging_path)


def _remove_owned_staging_directory(
    staging_path: str,
    marker: OwnershipMarker,
) -> None:
    if is_uninitialized_directory_claim(marker):
        root_stat = os.lstat(staging_path)
        if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
            raise StateError("Clone directory staging ownership identity is invalid.")
        shutil.rmtree(staging_path)
        return
    _remove_staging_directory_entries(staging_path, marker)


def _remove_marker_promotion(
    marker_path: str,
    task_id: str,
    artifact_type: str,
) -> None:
    marker_staging_path = ownership_marker_staging_path(marker_path, task_id)
    if not os.path.lexists(marker_staging_path):
        return
    require_ownership_marker(
        marker_staging_path,
        task_id,
        artifact_type,
        require_published=False,
    )
    os.unlink(marker_staging_path)
    fsync_directory(os.path.dirname(marker_path), strict=True)


def remove_owned_staging_artifact(
    staging_path: str,
    task_id: str,
    artifact_type: str,
) -> None:
    marker_path = artifact_ownership_marker_path(staging_path)
    if not os.path.lexists(marker_path):
        if os.path.lexists(staging_path):
            raise StateError("Clone staging artifact ownership marker is missing.")
        fsync_directory(os.path.dirname(staging_path), strict=True)
        return
    marker = require_ownership_marker(
        marker_path,
        task_id,
        artifact_type,
        require_published=False,
    )
    _remove_marker_promotion(marker_path, task_id, artifact_type)
    if os.path.lexists(staging_path):
        if artifact_type == "file":
            source_path = staging_path if marker.state == "claim" else None
            remove_file_artifact_atomically(staging_path, marker, source_path)
        elif artifact_type == "directory":
            _remove_owned_staging_directory(staging_path, marker)
        else:
            raise StateError("Clone staging artifact type is invalid.")
    os.unlink(marker_path)
    fsync_directory(os.path.dirname(staging_path), strict=True)


def release_staging_artifact_ownership(
    staging_path: str,
    task_id: str,
    artifact_type: str,
) -> None:
    if os.path.lexists(staging_path):
        raise StateError("Clone staging artifact still exists after publication.")
    marker_path = artifact_ownership_marker_path(staging_path)
    require_ownership_marker(
        marker_path,
        task_id,
        artifact_type,
        require_published=True,
    )
    _remove_marker_promotion(marker_path, task_id, artifact_type)
    os.unlink(marker_path)
    fsync_directory(os.path.dirname(staging_path), strict=True)
