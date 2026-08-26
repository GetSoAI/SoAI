"""SoAI - Atomic clone file artifact removal [backend/plugins/clone/file_artifact_removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.file_artifact_identity import (
    FileArtifactIdentity,
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.ownership_marker import (
    OwnershipEntry,
    OwnershipMarker,
    artifact_ownership_marker_path,
    read_ownership_marker,
    write_ownership_marker,
)
from plugins.clone.ownership_marker_builders import build_published_file_marker

__all__ = (
    "read_published_file_removal_marker",
    "remove_file_artifact_atomically",
    "remove_owned_file_entry_atomically",
)

_CAPTURED_ARTIFACT_NAME = "artifact"


def _require_safe_owner(owner: str) -> None:
    if not owner or any(character in owner for character in ("/", "\\", "\x00")):
        raise StateError("Clone file removal owner is invalid.")


def _capture_paths(final_path: str, owner: str) -> tuple[str, str, str]:
    _require_safe_owner(owner)
    capture_directory = f"{final_path}.soai-clone-removal-{owner}"
    return (
        capture_directory,
        os.path.join(capture_directory, _CAPTURED_ARTIFACT_NAME),
        artifact_ownership_marker_path(capture_directory),
    )


def read_published_file_removal_marker(
    final_path: str,
    owner: str,
) -> OwnershipMarker | None:
    _capture_directory, _captured_path, capture_marker_path = _capture_paths(
        final_path,
        owner,
    )
    if not os.path.lexists(capture_marker_path):
        return None
    marker = read_ownership_marker(capture_marker_path)
    if marker.owner != owner or marker.artifact_type != "file" or marker.state != "published":
        raise StateError("Clone file removal capture ownership mismatch.")
    return marker


def _prepare_capture_directory(
    final_path: str,
    marker: OwnershipMarker,
) -> tuple[str, str]:
    capture_directory, captured_path, capture_marker_path = _capture_paths(
        final_path,
        marker.owner,
    )
    marker_exists = os.path.lexists(capture_marker_path)
    if marker_exists and read_ownership_marker(capture_marker_path) != marker:
        raise StateError("Clone file removal capture ownership mismatch.")
    if not marker_exists:
        if os.path.lexists(capture_directory):
            raise StateError("Clone file removal capture ownership marker is missing.")
        write_ownership_marker(capture_marker_path, marker)
    try:
        os.mkdir(capture_directory, mode=0o700)
        fsync_directory(os.path.dirname(final_path), strict=True)
    except FileExistsError as exception:
        capture_stat = os.lstat(capture_directory)
        if not stat.S_ISDIR(capture_stat.st_mode):
            raise StateError("Clone file removal capture path is not a directory.") from exception
    return (capture_directory, captured_path)


def _expected_identity(
    marker: OwnershipMarker,
    staging_path: str | None,
) -> FileArtifactIdentity:
    if marker.state == "published":
        if marker.size_bytes is None or marker.sha256_hex is None:
            raise StateError("Clone file ownership content identity is missing.")
        return FileArtifactIdentity(
            device=marker.device,
            inode=marker.inode,
            size_bytes=marker.size_bytes,
            sha256_hex=marker.sha256_hex,
        )
    if staging_path is None or not os.path.lexists(staging_path):
        raise StateError("Clone file claim staging identity is missing.")
    return read_file_artifact_identity(staging_path)


def _require_expected_identity(path: str, expected: FileArtifactIdentity) -> None:
    identity = read_file_artifact_identity(path)
    if not file_artifact_identity_matches(
        identity,
        device=expected.device,
        inode=expected.inode,
        size_bytes=expected.size_bytes,
        sha256_hex=expected.sha256_hex,
    ):
        raise StateError("Clone file ownership identity mismatch.")


def remove_file_artifact_atomically(
    final_path: str,
    marker: OwnershipMarker,
    staging_path: str | None,
) -> None:
    expected = _expected_identity(marker, staging_path)
    _capture_directory, captured_path, _capture_marker_path = _capture_paths(
        final_path,
        marker.owner,
    )
    if not os.path.lexists(captured_path) and os.path.lexists(final_path):
        _require_expected_identity(final_path, expected)
    capture_directory, captured_path = _prepare_capture_directory(final_path, marker)
    if os.path.lexists(captured_path):
        _require_expected_identity(captured_path, expected)
    elif os.path.lexists(final_path):
        _require_expected_identity(final_path, expected)
        os.rename(final_path, captured_path)
        fsync_directory(capture_directory, strict=True)
        fsync_directory(os.path.dirname(final_path), strict=True)
        _require_expected_identity(captured_path, expected)
    if os.path.lexists(final_path):
        raise StateError("Clone file removal detected a foreign replacement.")
    if os.path.lexists(captured_path):
        os.unlink(captured_path)
        fsync_directory(capture_directory, strict=True)
    os.rmdir(capture_directory)
    capture_marker_path = artifact_ownership_marker_path(capture_directory)
    if read_ownership_marker(capture_marker_path) != marker:
        raise StateError("Clone file removal capture ownership mismatch.")
    os.unlink(capture_marker_path)
    fsync_directory(os.path.dirname(final_path), strict=True)


def remove_owned_file_entry_atomically(
    final_path: str,
    owner: str,
    entry: OwnershipEntry,
) -> None:
    remove_file_artifact_atomically(
        final_path,
        build_published_file_marker(
            owner,
            device=entry.device,
            inode=entry.inode,
            size_bytes=entry.size_bytes,
            sha256_hex=entry.sha256_hex,
        ),
        None,
    )
