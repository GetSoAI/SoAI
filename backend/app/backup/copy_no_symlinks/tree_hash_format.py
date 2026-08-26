"""SoAI - Stable tree hash format primitives (no symlinks) [backend/app/backup/copy_no_symlinks/tree_hash_format.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.backup.protocols import ByteHasherProtocol

__all__ = (
    "ByteHasherProtocol",
    "update_tree_hasher_for_relative_directory",
    "update_tree_hasher_for_relative_file",
)


def update_tree_hasher_for_relative_directory(
    hasher: ByteHasherProtocol,
    relative_root: str,
) -> None:
    hasher.update(b"D")
    hasher.update(relative_root.encode("utf-8"))
    hasher.update(b"\0")


def update_tree_hasher_for_relative_file(
    hasher: ByteHasherProtocol,
    relative_file: str,
    file_hash: str,
) -> None:
    hasher.update(b"F")
    hasher.update(relative_file.encode("utf-8"))
    hasher.update(b"\0")
    hasher.update(file_hash.encode("ascii"))
    hasher.update(b"\0")
