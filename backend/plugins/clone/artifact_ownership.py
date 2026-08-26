"""SoAI - Clone filesystem artifact ownership markers [backend/plugins/clone/artifact_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.file_artifact_removal import remove_file_artifact_atomically
from plugins.clone.ownership_marker import (
    OwnershipMarker,
    artifact_ownership_marker_path,
    replace_ownership_marker,
    require_ownership_marker,
    write_ownership_marker,
)
from plugins.clone.staging_artifact_ownership import (
    release_staging_artifact_ownership,
    require_staging_artifact_ownership,
)

__all__ = (
    "is_owned_file",
    "publish_file_no_clobber",
)


def is_owned_file(final_path: str, task_id: str) -> bool:
    marker_path = artifact_ownership_marker_path(final_path)
    if not os.path.lexists(marker_path):
        return False
    marker = require_ownership_marker(marker_path, task_id, "file", require_published=True)
    if not os.path.lexists(final_path):
        return False
    identity = read_file_artifact_identity(final_path)
    return file_artifact_identity_matches(
        identity,
        device=marker.device,
        inode=marker.inode,
        size_bytes=marker.size_bytes,
        sha256_hex=marker.sha256_hex,
    )


def publish_file_no_clobber(staging_path: str, final_path: str, task_id: str) -> None:
    require_staging_artifact_ownership(staging_path, task_id, "file")
    marker_path = artifact_ownership_marker_path(final_path)
    staging_identity = read_file_artifact_identity(staging_path)
    claim = OwnershipMarker(
        owner=task_id,
        artifact_type="file",
        state="claim",
        device=-1,
        inode=-1,
        size_bytes=None,
        sha256_hex=None,
    )
    published_marker = OwnershipMarker(
        owner=task_id,
        artifact_type="file",
        state="published",
        device=staging_identity.device,
        inode=staging_identity.inode,
        size_bytes=staging_identity.size_bytes,
        sha256_hex=staging_identity.sha256_hex,
    )
    write_ownership_marker(marker_path, claim)
    final_linked = False
    publication_complete = False
    try:
        os.link(staging_path, final_path, follow_symlinks=False)
        final_linked = True
        identity = read_file_artifact_identity(final_path)
        if not file_artifact_identity_matches(
            identity,
            device=staging_identity.device,
            inode=staging_identity.inode,
            size_bytes=staging_identity.size_bytes,
            sha256_hex=staging_identity.sha256_hex,
        ):
            raise StateError("Clone file ownership identity mismatch.")
        replace_ownership_marker(marker_path, published_marker)
        remove_file_artifact_atomically(staging_path, published_marker, None)
        release_staging_artifact_ownership(staging_path, task_id, "file")
        publication_complete = True
    finally:
        if not publication_complete:
            try:
                if final_linked and os.path.lexists(final_path):
                    remove_file_artifact_atomically(final_path, published_marker, None)
            finally:
                if os.path.lexists(marker_path):
                    require_ownership_marker(
                        marker_path,
                        task_id,
                        "file",
                        require_published=False,
                    )
                    os.unlink(marker_path)
                    fsync_directory(os.path.dirname(final_path), strict=True)
    fsync_directory(os.path.dirname(final_path), strict=True)
