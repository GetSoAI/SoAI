"""SoAI - Exact clone artifact ownership cleanup [backend/plugins/clone/artifact_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.directory_artifact_identity import (
    directory_artifact_identity_matches,
    read_directory_identity_entry,
)
from plugins.clone.directory_identity_release import (
    directory_identity_release_path,
    read_staged_directory_identity_removal,
    remove_staged_directory_identity,
    require_directory_identity_entry,
    require_directory_identity_release_state,
    stage_directory_identity_release,
)
from plugins.clone.directory_prepublication_cleanup import (
    is_uninitialized_directory_claim,
    recover_uninitialized_directory_claim,
    require_valid_unclaimed_directory_skeleton,
)
from plugins.clone.file_artifact_removal import (
    remove_file_artifact_atomically,
    remove_owned_file_entry_atomically,
)
from plugins.clone.nested_directory_removal import (
    remove_owned_nested_directory,
    remove_preclaimed_empty_directory,
)
from plugins.clone.ownership_marker import (
    DIRECTORY_IDENTITY,
    OwnershipMarker,
    artifact_ownership_marker_path,
    ownership_marker_staging_path,
    require_ownership_marker,
)

__all__ = (
    "remove_owned_directory",
    "remove_owned_file",
)


def _directory_removal_capture_path(path: str, task_id: str) -> str:
    return f"{path}.soai-clone-removal-{task_id}"


def _require_owned_empty_directory(
    path: str,
    *,
    device: int,
    inode: int,
) -> None:
    path_stat = os.lstat(path)
    if (
        not stat.S_ISDIR(path_stat.st_mode)
        or stat.S_ISLNK(path_stat.st_mode)
        or path_stat.st_dev != device
        or path_stat.st_ino != inode
        or os.listdir(path)
    ):
        raise StateError("Clone directory ownership identity mismatch.")


def _remove_owned_empty_directory(
    path: str,
    task_id: str,
    *,
    device: int,
    inode: int,
) -> None:
    capture_path = _directory_removal_capture_path(path, task_id)
    if os.path.lexists(capture_path):
        _require_owned_empty_directory(capture_path, device=device, inode=inode)
        if os.path.lexists(path):
            raise StateError("Clone directory removal detected a foreign replacement.")
    elif os.path.lexists(path):
        _require_owned_empty_directory(path, device=device, inode=inode)
        os.rename(path, capture_path)
        fsync_directory(os.path.dirname(path), strict=True)
        _require_owned_empty_directory(capture_path, device=device, inode=inode)
        if os.path.lexists(path):
            raise StateError("Clone directory removal detected a foreign replacement.")
    else:
        return
    try:
        os.rmdir(capture_path)
    except OSError as exception:
        raise StateError("Clone directory could not be removed atomically.") from exception
    fsync_directory(os.path.dirname(path), strict=True)


def _validate_marker_promotion(
    marker_path: str,
    task_id: str,
    artifact_type: str,
) -> tuple[str, OwnershipMarker] | None:
    staging_path = ownership_marker_staging_path(marker_path, task_id)
    if not os.path.lexists(staging_path):
        return None
    marker = require_ownership_marker(
        staging_path,
        task_id,
        artifact_type,
        require_published=False,
    )
    return (staging_path, marker)


def remove_owned_file(
    final_path: str,
    task_id: str,
    staging_path: str | None = None,
) -> None:
    marker_path = artifact_ownership_marker_path(final_path)
    marker = require_ownership_marker(
        marker_path,
        task_id,
        "file",
        require_published=False,
    )
    marker_promotion = _validate_marker_promotion(marker_path, task_id, "file")
    marker_staging_path = marker_promotion[0] if marker_promotion is not None else None
    if marker_staging_path is not None:
        os.unlink(marker_staging_path)
        fsync_directory(os.path.dirname(final_path), strict=True)
    remove_file_artifact_atomically(final_path, marker, staging_path)
    os.unlink(marker_path)
    fsync_directory(os.path.dirname(final_path), strict=True)


def remove_owned_directory(final_path: str, task_id: str, staging_path: str) -> None:
    marker_path = artifact_ownership_marker_path(final_path)
    if not os.path.lexists(marker_path):
        release_path = directory_identity_release_path(marker_path, task_id)
        if os.path.lexists(final_path):
            raise StateError("Clone artifact ownership identity mismatch.")
        release_identity = (
            read_directory_identity_entry(release_path, task_id)
            if os.path.lexists(release_path)
            else read_staged_directory_identity_removal(marker_path, task_id)
        )
        if release_identity is None:
            return
        remove_staged_directory_identity(
            marker_path,
            task_id,
            "staged",
            release_identity,
        )
        return
    marker = require_ownership_marker(
        marker_path,
        task_id,
        "directory",
        require_published=False,
    )
    marker_promotion = _validate_marker_promotion(marker_path, task_id, "directory")
    marker_staging_path = marker_promotion[0] if marker_promotion is not None else None
    if marker_promotion is not None and directory_artifact_identity_matches(
        final_path,
        marker_promotion[1],
    ):
        os.replace(marker_promotion[0], marker_path)
        fsync_directory(os.path.dirname(final_path), strict=True)
        marker = marker_promotion[1]
        marker_staging_path = None
    if is_uninitialized_directory_claim(marker):
        promoted = recover_uninitialized_directory_claim(
            final_path,
            marker_path,
            marker_staging_path,
            task_id,
        )
        if promoted is None:
            return
        marker = promoted
        marker_staging_path = None
    release_state = require_directory_identity_release_state(
        final_path,
        marker_path,
        task_id,
        marker,
        allow_missing_root=True,
    )
    if marker_staging_path is not None:
        os.unlink(marker_staging_path)
    if release_state in {"missing", "staged"} and not os.path.lexists(final_path):
        _remove_owned_empty_directory(
            final_path,
            task_id,
            device=marker.device,
            inode=marker.inode,
        )
        os.unlink(marker_path)
        fsync_directory(os.path.dirname(final_path), strict=True)
        remove_staged_directory_identity(
            marker_path,
            task_id,
            release_state,
            require_directory_identity_entry(marker),
        )
        return
    if release_state == "staged":
        stage_directory_identity_release(
            final_path,
            marker_path,
            task_id,
            marker,
            release_state,
        )
    require_valid_unclaimed_directory_skeleton(final_path, staging_path, marker)
    foreign_entries_remain = False
    entries_by_path = {entry.relative_path: entry for entry in marker.entries}
    for entry in reversed(marker.entries):
        if entry.relative_path == DIRECTORY_IDENTITY or entry.relative_path.endswith(
            f"/{DIRECTORY_IDENTITY}"
        ):
            continue
        entry_path = os.path.join(final_path, *entry.relative_path.split("/"))
        if entry.entry_type == "directory":
            try:
                if entry.device == -1 and entry.inode == -1:
                    remove_preclaimed_empty_directory(entry_path)
                else:
                    identity_entry = entries_by_path.get(
                        f"{entry.relative_path}/{DIRECTORY_IDENTITY}"
                    )
                    if identity_entry is None:
                        raise StateError("Clone nested directory identity is missing.")
                    remove_owned_nested_directory(
                        entry_path,
                        task_id,
                        entry,
                        identity_entry,
                    )
            except StateError:
                foreign_entries_remain = True
            continue
        if not os.path.lexists(entry_path):
            if entry.relative_path.endswith(f"/{DIRECTORY_IDENTITY}"):
                foreign_entries_remain = True
            continue
        try:
            remove_owned_file_entry_atomically(entry_path, task_id, entry)
        except StateError:
            foreign_entries_remain = True
    remaining_names = set(os.listdir(final_path))
    remaining_names.discard(DIRECTORY_IDENTITY)
    if remaining_names:
        foreign_entries_remain = True
    if foreign_entries_remain:
        raise StateError("Clone directory contains foreign entries after owned cleanup.")
    release_state = stage_directory_identity_release(
        final_path,
        marker_path,
        task_id,
        marker,
        release_state,
    )
    _remove_owned_empty_directory(
        final_path,
        task_id,
        device=marker.device,
        inode=marker.inode,
    )
    os.unlink(marker_path)
    fsync_directory(os.path.dirname(final_path), strict=True)
    remove_staged_directory_identity(
        marker_path,
        task_id,
        release_state,
        require_directory_identity_entry(marker),
    )
