"""SoAI - Clone artifact ownership marker construction [backend/plugins/clone/ownership_marker_builders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from plugins.clone.ownership_marker import OwnershipEntry, OwnershipMarker

__all__ = (
    "build_directory_claim_marker",
    "build_published_directory_marker",
    "build_published_file_marker",
)


def build_directory_claim_marker(
    owner: str,
    *,
    device: int,
    inode: int,
    entries: tuple[OwnershipEntry, ...] = (),
) -> OwnershipMarker:
    return OwnershipMarker(
        owner=owner,
        artifact_type="directory",
        state="claim",
        device=device,
        inode=inode,
        size_bytes=None,
        sha256_hex=None,
        entries=entries,
    )


def build_published_directory_marker(
    owner: str,
    *,
    device: int,
    inode: int,
    entries: tuple[OwnershipEntry, ...] = (),
) -> OwnershipMarker:
    return OwnershipMarker(
        owner=owner,
        artifact_type="directory",
        state="published",
        device=device,
        inode=inode,
        size_bytes=None,
        sha256_hex=None,
        entries=entries,
    )


def build_published_file_marker(
    owner: str,
    *,
    device: int,
    inode: int,
    size_bytes: int | None,
    sha256_hex: str | None,
) -> OwnershipMarker:
    return OwnershipMarker(
        owner=owner,
        artifact_type="file",
        state="published",
        device=device,
        inode=inode,
        size_bytes=size_bytes,
        sha256_hex=sha256_hex,
    )
