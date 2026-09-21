"""SoAI - Shared archive extraction constants and helpers [backend/core/archives/constants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.archives.errors import ArchivePathTraversalError
from core.validation.requirements import require_non_negative_exact_int

__all__ = ()

MAX_SYMLINK_CHAIN_DEPTH: int = 20
CHUNK_READ_SIZE: int = 65536
UNIX_MODE_MASK: int = 0xFFFF
UNIX_MODE_TYPE_MASK: int = 0o170000
UNIX_MODE_SYMLINK: int = 0o120000


def validate_member_name(member_name: str) -> str:
    if os.path.isabs(member_name):
        raise ArchivePathTraversalError(f"Archive member has absolute path: {member_name}")
    normalized_for_validation = member_name.replace("\\", "/")
    if normalized_for_validation.startswith("/"):
        raise ArchivePathTraversalError(f"Archive member has absolute path: {member_name}")
    if len(normalized_for_validation) >= 2 and normalized_for_validation[1] == ":":
        raise ArchivePathTraversalError(f"Archive member has absolute path: {member_name}")
    if any(part in {".", ".."} for part in normalized_for_validation.split("/")):
        raise ArchivePathTraversalError(f"Archive member has path traversal segment: {member_name}")
    normalized = os.path.normpath(normalized_for_validation)
    if normalized in {"", "."}:
        raise ArchivePathTraversalError(f"Archive member has empty path: {member_name}")
    if normalized == ".." or normalized.startswith(f"..{os.sep}"):
        raise ArchivePathTraversalError(f"Archive member escapes destination: {member_name}")
    return normalized


def accumulate_size(current: int, additional: int, name: str) -> int:
    normalized_current = require_non_negative_exact_int(
        current,
        type_message="Archive accumulated size must be an integer.",
        range_message="Archive accumulated size must not be negative.",
    )
    normalized_additional = require_non_negative_exact_int(
        additional,
        type_message=f"Archive member size must be an integer: {name}",
        range_message=f"Archive member size must not be negative: {name}",
    )
    total = normalized_current + normalized_additional
    return total


def ensure_parent_exists(file_path: str) -> None:
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
