"""SoAI - Atomic clone directory artifact publication [backend/plugins/clone/directory_artifact_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError
from core.filesystem.atomic_write_primitives import fsync_directory
from plugins.clone.artifact_cleanup import remove_owned_directory
from plugins.clone.directory_artifact_identity import create_directory_identity
from plugins.clone.directory_prepublication_cleanup import (
    remove_empty_staging_tree,
    restore_published_entries,
)
from plugins.clone.directory_publication_ownership import (
    PublishedDirectoryEntry,
    build_claimed_ownership_entries,
    build_published_ownership_entries,
)
from plugins.clone.file_artifact_identity import (
    file_artifact_identity_matches,
    read_file_artifact_identity,
)
from plugins.clone.file_artifact_removal import remove_file_artifact_atomically
from plugins.clone.ownership_marker import (
    DIRECTORY_IDENTITY,
    OwnershipEntry,
    artifact_ownership_marker_path,
    replace_ownership_marker,
    require_ownership_marker,
    write_ownership_marker,
)
from plugins.clone.ownership_marker_builders import (
    build_directory_claim_marker,
    build_published_directory_marker,
    build_published_file_marker,
)
from plugins.clone.staging_artifact_ownership import (
    release_staging_artifact_ownership,
    require_staging_artifact_ownership,
)

__all__ = ("claim_directory_publication",)


def _require_publication_root(final_path: str, device: int, inode: int) -> None:
    try:
        root_stat = os.lstat(final_path)
    except FileNotFoundError as exception:
        raise StateError("Clone directory publication root is missing.") from exception
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or stat.S_ISLNK(root_stat.st_mode)
        or root_stat.st_dev != device
        or root_stat.st_ino != inode
    ):
        raise StateError("Clone directory publication root changed.")


def _create_directory_skeleton(
    source_directory: str,
    final_directory: str,
    published_entries: list[PublishedDirectoryEntry],
    task_id: str,
) -> None:
    for entry_name in sorted(os.listdir(source_directory)):
        source_path = os.path.join(source_directory, entry_name)
        final_path = os.path.join(final_directory, entry_name)
        source_stat = os.lstat(source_path)
        if stat.S_ISREG(source_stat.st_mode):
            continue
        if stat.S_ISDIR(source_stat.st_mode):
            os.mkdir(final_path, mode=stat.S_IMODE(source_stat.st_mode))
            final_stat = os.lstat(final_path)
            directory_identity = create_directory_identity(final_path, task_id)
            published_entries.append(
                PublishedDirectoryEntry(
                    source_path=source_path,
                    final_path=final_path,
                    device=final_stat.st_dev,
                    inode=final_stat.st_ino,
                    is_directory=True,
                    size_bytes=None,
                    sha256_hex=None,
                    directory_identity=directory_identity,
                )
            )
            _create_directory_skeleton(source_path, final_path, published_entries, task_id)
            continue
        raise StateError(f"Clone staging tree contains an unsupported entry: {source_path}")


def _publish_files_no_clobber(
    source_directory: str,
    final_directory: str,
    published_entries: list[PublishedDirectoryEntry],
    ownership_by_relative_path: dict[str, OwnershipEntry],
    publication_root: str,
    task_id: str,
) -> None:
    for entry_name in sorted(os.listdir(source_directory)):
        source_path = os.path.join(source_directory, entry_name)
        final_path = os.path.join(final_directory, entry_name)
        source_stat = os.lstat(source_path)
        if stat.S_ISDIR(source_stat.st_mode):
            _publish_files_no_clobber(
                source_path,
                final_path,
                published_entries,
                ownership_by_relative_path,
                publication_root,
                task_id,
            )
            continue
        if not stat.S_ISREG(source_stat.st_mode):
            raise StateError(f"Clone staging tree contains an unsupported entry: {source_path}")
        os.link(source_path, final_path, follow_symlinks=False)
        identity = read_file_artifact_identity(final_path)
        relative_path = os.path.relpath(final_path, publication_root).replace(os.sep, "/")
        ownership = ownership_by_relative_path.get(relative_path)
        if ownership is None or ownership.entry_type != "file":
            raise StateError("Clone directory publication contains an unowned file.")
        if not file_artifact_identity_matches(
            identity,
            device=ownership.device,
            inode=ownership.inode,
            size_bytes=ownership.size_bytes,
            sha256_hex=ownership.sha256_hex,
        ):
            raise StateError("Clone directory publication entry identity changed.")
        published_entries.append(
            PublishedDirectoryEntry(
                source_path=source_path,
                final_path=final_path,
                device=identity.device,
                inode=identity.inode,
                is_directory=False,
                size_bytes=identity.size_bytes,
                sha256_hex=identity.sha256_hex,
                directory_identity=None,
            )
        )
        remove_file_artifact_atomically(
            source_path,
            build_published_file_marker(
                task_id,
                device=identity.device,
                inode=identity.inode,
                size_bytes=identity.size_bytes,
                sha256_hex=identity.sha256_hex,
            ),
            None,
        )


def _fsync_published_directories(
    final_directory: str,
    published_entries: list[PublishedDirectoryEntry],
) -> None:
    for published in reversed(published_entries):
        if published.is_directory:
            fsync_directory(published.final_path, strict=True)
    fsync_directory(final_directory, strict=True)


def claim_directory_publication(staging_path: str, final_path: str, task_id: str) -> None:
    staging_marker = require_staging_artifact_ownership(staging_path, task_id, "directory")
    marker_path = artifact_ownership_marker_path(final_path)
    marker_created = False
    root_created = False
    identity_entry: OwnershipEntry | None = None
    published_entries: list[PublishedDirectoryEntry] = []
    publication_complete = False
    try:
        write_ownership_marker(
            marker_path,
            build_directory_claim_marker(
                task_id,
                device=-1,
                inode=-1,
            ),
        )
        marker_created = True
        os.mkdir(final_path, mode=0o750)
        root_created = True
        identity_entry = create_directory_identity(final_path, task_id)
        root_stat = os.lstat(final_path)
        _require_publication_root(final_path, root_stat.st_dev, root_stat.st_ino)
        fsync_directory(final_path, strict=True)
        ownership_entries = staging_marker.entries
        if any(DIRECTORY_IDENTITY in entry.relative_path.split("/") for entry in ownership_entries):
            raise StateError("Clone staging tree contains the reserved directory identity path.")
        claim = build_directory_claim_marker(
            task_id,
            device=root_stat.st_dev,
            inode=root_stat.st_ino,
            entries=(identity_entry, *ownership_entries),
        )
        replace_ownership_marker(marker_path, claim)
        _create_directory_skeleton(staging_path, final_path, published_entries, task_id)
        _fsync_published_directories(final_path, published_entries)
        _require_publication_root(final_path, root_stat.st_dev, root_stat.st_ino)
        replace_ownership_marker(
            marker_path,
            build_directory_claim_marker(
                task_id,
                device=root_stat.st_dev,
                inode=root_stat.st_ino,
                entries=(
                    identity_entry,
                    *build_claimed_ownership_entries(
                        ownership_entries,
                        published_entries,
                        final_path,
                    ),
                ),
            ),
        )
        _publish_files_no_clobber(
            staging_path,
            final_path,
            published_entries,
            {entry.relative_path: entry for entry in ownership_entries},
            final_path,
            task_id,
        )
        _fsync_published_directories(final_path, published_entries)
        _require_publication_root(final_path, root_stat.st_dev, root_stat.st_ino)
        published_ownership = build_published_ownership_entries(
            ownership_entries,
            published_entries,
            final_path,
        )
        replace_ownership_marker(
            marker_path,
            build_published_directory_marker(
                task_id,
                device=root_stat.st_dev,
                inode=root_stat.st_ino,
                entries=(identity_entry, *published_ownership),
            ),
        )
        remove_empty_staging_tree(staging_path, published_entries)
        release_staging_artifact_ownership(staging_path, task_id, "directory")
        fsync_directory(os.path.dirname(final_path), strict=True)
        publication_complete = True
    finally:
        if not publication_complete:
            try:
                if os.path.lexists(staging_path):
                    restore_published_entries(published_entries, task_id)
            finally:
                if marker_created and root_created:
                    remove_owned_directory(
                        final_path,
                        task_id,
                        staging_path,
                    )
                elif marker_created:
                    require_ownership_marker(
                        marker_path,
                        task_id,
                        "directory",
                        require_published=False,
                    )
                    os.unlink(marker_path)
                    fsync_directory(os.path.dirname(final_path), strict=True)
