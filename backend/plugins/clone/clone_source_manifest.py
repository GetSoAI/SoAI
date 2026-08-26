"""SoAI - Secure clone source-tree manifests [backend/plugins/clone/clone_source_manifest.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from typing import Literal

from core.errors.exceptions import StateError, ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.files.secure_open_flags import secure_read_only_open_flags

__all__ = (
    "CloneSourceEntry",
    "CloneSourceSnapshot",
    "build_clone_source_snapshot",
    "inspect_secure_directory_source",
    "scan_clone_source",
)

FILESYSTEM_ENTRY_CAPACITY_BYTES = 4096


@dataclass(frozen=True, slots=True)
class CloneSourceEntry:
    relative_path: str
    entry_type: Literal["directory", "file"]
    size_bytes: int
    device: int
    inode: int
    modified_ns: int
    mode: int
    content_digest: bytes | None


@dataclass(frozen=True, slots=True)
class CloneSourceSnapshot:
    required_bytes: int
    source_digest: bytes


def _file_digest(handle: int) -> bytes:
    return bytes.fromhex(hash_descriptor_content(handle).sha256_hex)


def _source_digest(entries: tuple[CloneSourceEntry, ...]) -> bytes:
    digest = hashlib.sha256()
    for entry in entries:
        values = (
            entry.relative_path,
            entry.entry_type,
            str(entry.size_bytes),
            str(entry.device),
            str(entry.inode),
            str(entry.modified_ns),
            str(entry.mode),
        )
        for value in values:
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        content_digest = entry.content_digest or b""
        digest.update(len(content_digest).to_bytes(8, "big"))
        digest.update(content_digest)
    return digest.digest()


def build_clone_source_snapshot(
    manifest: tuple[CloneSourceEntry, ...],
) -> CloneSourceSnapshot:
    metadata_bytes = FILESYSTEM_ENTRY_CAPACITY_BYTES
    for entry in manifest:
        metadata_bytes += FILESYSTEM_ENTRY_CAPACITY_BYTES + (
            2 * len(entry.relative_path.encode("utf-8"))
        )
    return CloneSourceSnapshot(
        required_bytes=sum(entry.size_bytes for entry in manifest) + metadata_bytes,
        source_digest=_source_digest(manifest),
    )


def scan_clone_source(root_handle: int) -> tuple[CloneSourceEntry, ...]:
    source_entries: list[CloneSourceEntry] = []
    seen_inodes: set[tuple[int, int]] = set()

    def scan(directory_handle: int, relative_directory: str) -> None:
        with os.scandir(directory_handle) as entries:
            for entry in sorted(entries, key=lambda candidate: candidate.name):
                relative_path = os.path.join(relative_directory, entry.name)
                entry_stat = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(entry_stat.st_mode):
                    raise ValidationError(
                        f"Clone model source contains a symbolic link: {relative_path}"
                    )
                if stat.S_ISDIR(entry_stat.st_mode):
                    source_entries.append(
                        CloneSourceEntry(
                            relative_path=relative_path,
                            entry_type="directory",
                            size_bytes=0,
                            device=entry_stat.st_dev,
                            inode=entry_stat.st_ino,
                            modified_ns=entry_stat.st_mtime_ns,
                            mode=entry_stat.st_mode,
                            content_digest=None,
                        )
                    )
                    child_handle = os.open(
                        entry.name,
                        secure_read_only_open_flags(directory=True),
                        dir_fd=directory_handle,
                    )
                    try:
                        opened_stat = os.fstat(child_handle)
                        if (
                            opened_stat.st_dev != entry_stat.st_dev
                            or opened_stat.st_ino != entry_stat.st_ino
                        ):
                            raise StateError(
                                f"Clone model source changed during scan: {relative_path}"
                            )
                        scan(child_handle, relative_path)
                    finally:
                        os.close(child_handle)
                    continue
                if not stat.S_ISREG(entry_stat.st_mode):
                    raise ValidationError(
                        f"Clone model source contains a special file: {relative_path}"
                    )
                identity = (entry_stat.st_dev, entry_stat.st_ino)
                if entry_stat.st_nlink != 1 or identity in seen_inodes:
                    raise ValidationError(
                        f"Clone model source contains a hardlink alias: {relative_path}"
                    )
                seen_inodes.add(identity)
                file_handle = os.open(
                    entry.name,
                    secure_read_only_open_flags(directory=False),
                    dir_fd=directory_handle,
                )
                try:
                    opened_stat = os.fstat(file_handle)
                    if (
                        opened_stat.st_dev != entry_stat.st_dev
                        or opened_stat.st_ino != entry_stat.st_ino
                        or opened_stat.st_size != entry_stat.st_size
                        or opened_stat.st_mtime_ns != entry_stat.st_mtime_ns
                        or not stat.S_ISREG(opened_stat.st_mode)
                    ):
                        raise StateError(f"Clone model source changed during scan: {relative_path}")
                    content_digest = _file_digest(file_handle)
                    final_stat = os.fstat(file_handle)
                    if (
                        final_stat.st_size != opened_stat.st_size
                        or final_stat.st_mtime_ns != opened_stat.st_mtime_ns
                    ):
                        raise StateError(f"Clone model source changed during scan: {relative_path}")
                finally:
                    os.close(file_handle)
                source_entries.append(
                    CloneSourceEntry(
                        relative_path=relative_path,
                        entry_type="file",
                        size_bytes=entry_stat.st_size,
                        device=entry_stat.st_dev,
                        inode=entry_stat.st_ino,
                        modified_ns=entry_stat.st_mtime_ns,
                        mode=entry_stat.st_mode,
                        content_digest=content_digest,
                    )
                )

    scan(root_handle, "")
    return tuple(source_entries)


def inspect_secure_directory_source(source: str) -> CloneSourceSnapshot:
    if os.name == "nt":
        raise StateError("Secure clone copying requires directory-relative no-follow support.")
    source_handle = os.open(
        source,
        secure_read_only_open_flags(directory=True),
    )
    try:
        manifest = scan_clone_source(source_handle)
        return build_clone_source_snapshot(manifest)
    finally:
        os.close(source_handle)
