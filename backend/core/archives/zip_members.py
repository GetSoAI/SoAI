"""SoAI - Zip archive member validation helpers [backend/core/archives/zip_members.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import fnmatch
import os
import posixpath
import zipfile
from collections.abc import Sequence

from core.archives.constants import (
    UNIX_MODE_MASK,
    UNIX_MODE_SYMLINK,
    UNIX_MODE_TYPE_MASK,
)
from core.archives.errors import ArchivePathTraversalError

__all__ = ()


def detect_root_prefix(members: list[zipfile.ZipInfo]) -> str | None:
    for entry in members:
        posix_name = entry.filename.replace("\\", "/").strip("/")
        normalized = posixpath.normpath(posix_name) if posix_name else ""
        if normalized and normalized not in {".", ".."}:
            return normalized.split("/", 1)[0]
    return None


def normalize_zip_member_path(
    posix_name: str,
    root_prefix: str | None,
    *,
    strip_root: bool,
) -> str:
    normalized_for_validation = posix_name.replace("\\", "/")
    if posixpath.isabs(normalized_for_validation):
        raise ArchivePathTraversalError(f"Unsafe absolute path detected in archive: {posix_name}")
    if len(normalized_for_validation) >= 2 and normalized_for_validation[1] == ":":
        raise ArchivePathTraversalError(f"Unsafe absolute path detected in archive: {posix_name}")
    if any(part in {".", ".."} for part in normalized_for_validation.split("/")):
        raise ArchivePathTraversalError(f"Unsafe path detected in archive: {posix_name}")
    normalized = posixpath.normpath(posix_name) if posix_name else ""
    if not normalized or normalized in {".", ""}:
        return ""
    if normalized == ".." or normalized.startswith("../"):
        raise ArchivePathTraversalError(f"Unsafe path detected in archive: {posix_name}")
    parts = [part for part in normalized.split("/") if part]
    if strip_root and root_prefix and parts and parts[0] == root_prefix:
        parts = parts[1:]
    relative_path = os.path.normpath(os.path.join(*parts)) if parts else ""
    if not relative_path or relative_path == ".":
        return ""
    if (
        os.path.isabs(relative_path)
        or relative_path.startswith(f"..{os.sep}")
        or f"..{os.sep}" in relative_path
    ):
        raise ArchivePathTraversalError(f"Unsafe path detected in archive: {posix_name}")
    return relative_path


def should_skip_member(relative_path: str, ignore_patterns: Sequence[str]) -> bool:
    if not ignore_patterns:
        return False
    path_parts = relative_path.split(os.sep)
    return any(fnmatch.fnmatch(part, pattern) for pattern in ignore_patterns for part in path_parts)


def should_skip_top_level_member(
    relative_path: str,
    top_level_ignore_patterns: Sequence[str],
) -> bool:
    if not top_level_ignore_patterns:
        return False
    top_level_item = relative_path.split(os.sep, 1)[0]
    return any(fnmatch.fnmatch(top_level_item, pattern) for pattern in top_level_ignore_patterns)


def validate_zip_member_symlink(member: zipfile.ZipInfo) -> None:
    unix_mode = (member.external_attr >> 16) & UNIX_MODE_MASK
    is_symlink = (unix_mode & UNIX_MODE_TYPE_MASK) == UNIX_MODE_SYMLINK
    if is_symlink:
        raise ArchivePathTraversalError(f"Archive contains symlink: {member.filename}")
