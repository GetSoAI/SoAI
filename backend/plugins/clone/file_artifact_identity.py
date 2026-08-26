"""SoAI - Exact clone file artifact identity [backend/plugins/clone/file_artifact_identity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from core.errors.exceptions import StateError, ValidationError
from core.files.content_hashing import hash_descriptor_content
from core.filesystem.open_files import open_regular_binary_no_symlink

__all__ = (
    "FileArtifactIdentity",
    "file_artifact_identity_matches",
    "read_file_artifact_identity",
)


@dataclass(frozen=True, slots=True)
class FileArtifactIdentity:
    device: int
    inode: int
    size_bytes: int
    sha256_hex: str


def file_artifact_identity_matches(
    identity: FileArtifactIdentity,
    *,
    device: int,
    inode: int,
    size_bytes: int | None,
    sha256_hex: str | None,
) -> bool:
    return (
        size_bytes is not None
        and sha256_hex is not None
        and identity.device == device
        and identity.inode == inode
        and identity.size_bytes == size_bytes
        and identity.sha256_hex == sha256_hex
    )


def _stable_stat_fields(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def read_file_artifact_identity(path: str) -> FileArtifactIdentity:
    try:
        with open_regular_binary_no_symlink(
            path,
            not_found_message="Clone file ownership identity is unavailable.",
            symlink_message="Clone file ownership identity mismatch.",
            open_message="Clone file ownership identity is unavailable.",
            inspect_message="Clone file ownership identity is unavailable.",
            regular_file_message="Clone file ownership identity mismatch.",
        ) as file_handle:
            descriptor = file_handle.fileno()
            descriptor_before = os.fstat(descriptor)
            path_before = os.lstat(path)
            if (
                not stat.S_ISREG(path_before.st_mode)
                or descriptor_before.st_dev != path_before.st_dev
                or descriptor_before.st_ino != path_before.st_ino
            ):
                raise StateError("Clone file ownership identity mismatch.")
            content_hash = hash_descriptor_content(descriptor)
            descriptor_after = os.fstat(descriptor)
            path_after = os.lstat(path)
    except FileNotFoundError as exception:
        raise StateError("Clone file ownership identity mismatch.") from exception
    except OSError as exception:
        raise StateError("Clone file ownership identity is unavailable.") from exception
    except ValidationError as exception:
        raise StateError(str(exception)) from exception
    if (
        _stable_stat_fields(descriptor_before) != _stable_stat_fields(descriptor_after)
        or descriptor_after.st_dev != path_after.st_dev
        or descriptor_after.st_ino != path_after.st_ino
        or not stat.S_ISREG(path_after.st_mode)
        or content_hash.size_bytes != descriptor_after.st_size
    ):
        raise StateError("Clone file changed during ownership validation.")
    return FileArtifactIdentity(
        device=descriptor_after.st_dev,
        inode=descriptor_after.st_ino,
        size_bytes=content_hash.size_bytes,
        sha256_hex=content_hash.sha256_hex,
    )
