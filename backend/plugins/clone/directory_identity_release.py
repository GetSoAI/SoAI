"""SoAI - Durable clone directory identity release [backend/plugins/clone/directory_identity_release.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.directory_artifact_identity import read_directory_identity_entry
from plugins.clone.file_artifact_removal import (
    read_published_file_removal_marker,
    remove_file_artifact_atomically,
)
from plugins.clone.ownership_marker import (
    DIRECTORY_IDENTITY,
    OwnershipEntry,
    OwnershipMarker,
)
from plugins.clone.ownership_marker_builders import build_published_file_marker

__all__ = (
    "directory_identity_release_path",
    "remove_staged_directory_identity",
    "require_directory_identity_entry",
    "require_directory_identity_release_state",
    "read_staged_directory_identity_removal",
    "stage_directory_identity_release",
)


if TYPE_CHECKING:
    from typing import Literal

    type DirectoryIdentityReleaseState = Literal["linked", "missing", "owned", "staged"]


def directory_identity_release_path(marker_path: str, task_id: str) -> str:
    return f"{marker_path}.release-identity-{task_id}"


def read_staged_directory_identity_removal(
    marker_path: str,
    task_id: str,
) -> OwnershipEntry | None:
    marker = read_published_file_removal_marker(
        directory_identity_release_path(marker_path, task_id),
        task_id,
    )
    if marker is None:
        return None
    return OwnershipEntry(
        relative_path=DIRECTORY_IDENTITY,
        entry_type="file",
        device=marker.device,
        inode=marker.inode,
        size_bytes=marker.size_bytes,
        sha256_hex=marker.sha256_hex,
    )


def require_directory_identity_entry(marker: OwnershipMarker) -> OwnershipEntry:
    identity_entries = tuple(
        entry for entry in marker.entries if entry.relative_path == DIRECTORY_IDENTITY
    )
    if len(identity_entries) != 1 or identity_entries[0].entry_type != "file":
        raise StateError("Clone directory ownership identity record is invalid.")
    return identity_entries[0]


def require_directory_identity_release_state(
    final_path: str,
    marker_path: str,
    task_id: str,
    marker: OwnershipMarker,
    *,
    allow_missing_root: bool,
) -> DirectoryIdentityReleaseState:
    identity_path = os.path.join(final_path, DIRECTORY_IDENTITY)
    release_path = directory_identity_release_path(marker_path, task_id)
    release_exists = os.path.lexists(release_path)
    expected_identity = require_directory_identity_entry(marker)
    try:
        root_stat = os.lstat(final_path)
    except FileNotFoundError as exception:
        if not allow_missing_root:
            raise StateError("Clone artifact ownership identity mismatch.") from exception
        if release_exists:
            if read_directory_identity_entry(release_path, task_id) != expected_identity:
                raise StateError("Clone artifact ownership identity mismatch.") from exception
            return "staged"
        return "missing"
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or root_stat.st_dev != marker.device
        or root_stat.st_ino != marker.inode
    ):
        raise StateError("Clone artifact ownership identity mismatch.")
    identity_exists = os.path.lexists(identity_path)
    if not identity_exists and not release_exists:
        raise StateError("Clone artifact ownership identity mismatch.")
    if identity_exists:
        observed_identity = read_directory_identity_entry(identity_path, task_id)
        if observed_identity != expected_identity:
            raise StateError("Clone artifact ownership identity mismatch.")
    if release_exists:
        observed_release = read_directory_identity_entry(release_path, task_id)
        if observed_release != expected_identity:
            raise StateError("Clone artifact ownership identity mismatch.")
    if identity_exists and release_exists:
        return "linked"
    return "owned" if identity_exists else "staged"


def stage_directory_identity_release(
    final_path: str,
    marker_path: str,
    task_id: str,
    marker: OwnershipMarker,
    release_state: DirectoryIdentityReleaseState,
) -> DirectoryIdentityReleaseState:
    identity_path = os.path.join(final_path, DIRECTORY_IDENTITY)
    release_path = directory_identity_release_path(marker_path, task_id)
    expected_identity = require_directory_identity_entry(marker)
    if release_state == "owned":
        os.link(identity_path, release_path, follow_symlinks=False)
        fsync_directory(os.path.dirname(final_path), strict=True)
        if read_directory_identity_entry(release_path, task_id) != expected_identity:
            raise StateError("Clone artifact ownership identity mismatch.")
        release_state = "linked"
    if release_state in {"linked", "staged"}:
        remove_file_artifact_atomically(
            identity_path,
            build_published_file_marker(
                task_id,
                device=expected_identity.device,
                inode=expected_identity.inode,
                size_bytes=expected_identity.size_bytes,
                sha256_hex=expected_identity.sha256_hex,
            ),
            None,
        )
        release_state = "staged"
    return release_state


def remove_staged_directory_identity(
    marker_path: str,
    task_id: str,
    release_state: DirectoryIdentityReleaseState,
    expected_identity: OwnershipEntry,
) -> None:
    if release_state != "staged":
        return
    remove_file_artifact_atomically(
        directory_identity_release_path(marker_path, task_id),
        build_published_file_marker(
            task_id,
            device=expected_identity.device,
            inode=expected_identity.inode,
            size_bytes=expected_identity.size_bytes,
            sha256_hex=expected_identity.sha256_hex,
        ),
        None,
    )
