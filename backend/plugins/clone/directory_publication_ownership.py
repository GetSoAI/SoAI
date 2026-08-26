"""SoAI - Clone directory publication ownership projection [backend/plugins/clone/directory_publication_ownership.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from core.errors.exceptions import StateError
from plugins.clone.file_artifact_identity import read_file_artifact_identity
from plugins.clone.ownership_marker import DIRECTORY_IDENTITY, OwnershipEntry

__all__ = (
    "PublishedDirectoryEntry",
    "build_claimed_ownership_entries",
    "build_directory_ownership_entries",
    "build_published_ownership_entries",
)


@dataclass(frozen=True, slots=True)
class PublishedDirectoryEntry:
    source_path: str
    final_path: str
    device: int
    inode: int
    is_directory: bool
    size_bytes: int | None
    sha256_hex: str | None
    directory_identity: OwnershipEntry | None = None


def _published_directory_ownership(
    published: PublishedDirectoryEntry,
    relative_path: str,
) -> tuple[OwnershipEntry, OwnershipEntry]:
    identity = published.directory_identity
    if identity is None:
        raise StateError("Clone directory publication identity is missing.")
    return (
        OwnershipEntry(relative_path, "directory", published.device, published.inode, None, None),
        OwnershipEntry(
            f"{relative_path}/{DIRECTORY_IDENTITY}",
            "file",
            identity.device,
            identity.inode,
            identity.size_bytes,
            identity.sha256_hex,
        ),
    )


def build_directory_ownership_entries(root_path: str) -> tuple[OwnershipEntry, ...]:
    entries: list[OwnershipEntry] = []
    for current_root, directory_names, file_names in os.walk(root_path, followlinks=False):
        directory_names.sort()
        file_names.sort()
        relative_root = os.path.relpath(current_root, root_path)
        prefix = "" if relative_root == "." else relative_root.replace(os.sep, "/")
        for directory_name in directory_names:
            path = os.path.join(current_root, directory_name)
            path_stat = os.lstat(path)
            if not stat.S_ISDIR(path_stat.st_mode):
                raise StateError("Clone staging tree contains an unsupported directory entry.")
            relative_path = f"{prefix}/{directory_name}" if prefix else directory_name
            entries.append(OwnershipEntry(relative_path, "directory", -1, -1, None, None))
        for file_name in file_names:
            path = os.path.join(current_root, file_name)
            identity = read_file_artifact_identity(path)
            relative_path = f"{prefix}/{file_name}" if prefix else file_name
            entries.append(
                OwnershipEntry(
                    relative_path,
                    "file",
                    identity.device,
                    identity.inode,
                    identity.size_bytes,
                    identity.sha256_hex,
                )
            )
    return tuple(entries)


def build_published_ownership_entries(
    ownership_entries: tuple[OwnershipEntry, ...],
    published_entries: list[PublishedDirectoryEntry],
    final_directory: str,
) -> tuple[OwnershipEntry, ...]:
    expected = {entry.relative_path: entry for entry in ownership_entries}
    if len(expected) != len(published_entries):
        raise StateError("Clone directory publication changed during ownership transfer.")
    published_ownership: list[OwnershipEntry] = []
    for published in published_entries:
        relative_path = os.path.relpath(published.final_path, final_directory).replace(
            os.sep,
            "/",
        )
        ownership = expected.get(relative_path)
        if ownership is None:
            raise StateError("Clone directory publication contains an unowned entry.")
        expected_type = "directory" if published.is_directory else "file"
        if ownership.entry_type != expected_type:
            raise StateError("Clone directory publication entry type changed.")
        if not published.is_directory and (
            ownership.device != published.device
            or ownership.inode != published.inode
            or ownership.size_bytes != published.size_bytes
            or ownership.sha256_hex != published.sha256_hex
        ):
            raise StateError("Clone directory publication entry identity changed.")
        if published.is_directory:
            published_ownership.extend(_published_directory_ownership(published, relative_path))
        else:
            published_ownership.append(
                OwnershipEntry(
                    relative_path=relative_path,
                    entry_type=expected_type,
                    device=published.device,
                    inode=published.inode,
                    size_bytes=published.size_bytes,
                    sha256_hex=published.sha256_hex,
                )
            )
    return tuple(published_ownership)


def build_claimed_ownership_entries(
    ownership_entries: tuple[OwnershipEntry, ...],
    published_entries: list[PublishedDirectoryEntry],
    final_directory: str,
) -> tuple[OwnershipEntry, ...]:
    published_directories = {
        os.path.relpath(entry.final_path, final_directory).replace(os.sep, "/"): entry
        for entry in published_entries
        if entry.is_directory
    }
    expected_directory_count = sum(entry.entry_type == "directory" for entry in ownership_entries)
    if len(published_directories) != expected_directory_count:
        raise StateError("Clone directory skeleton changed during ownership transfer.")
    claimed_entries: list[OwnershipEntry] = []
    for ownership in ownership_entries:
        if ownership.entry_type == "file":
            claimed_entries.append(ownership)
            continue
        published = published_directories.get(ownership.relative_path)
        if published is None:
            raise StateError("Clone directory skeleton contains an unowned entry.")
        claimed_entries.extend(_published_directory_ownership(published, ownership.relative_path))
    return tuple(claimed_entries)
