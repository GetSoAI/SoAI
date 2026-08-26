"""SoAI - Signed software release manifest records [backend/app/updater/release_manifest_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "ReleaseIdentity",
    "ReleaseFileRecord",
    "ReleaseInstaller",
    "ReleaseLegalFingerprint",
    "ReleaseManifestV1",
    "ReleasePublicationRecord",
    "ReleasePublicTrust",
    "ReleaseUpdateArchive",
)


@dataclass(frozen=True, slots=True)
class ReleaseFileRecord:
    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ReleaseUpdateArchive:
    name: str
    platforms: tuple[str, ...]
    size_bytes: int
    sha256: str
    archive_root: str
    files: tuple[ReleaseFileRecord, ...]


@dataclass(frozen=True, slots=True)
class ReleaseInstaller:
    name: str
    platforms: tuple[str, ...]
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ReleasePublicationRecord:
    public_core_commit: str
    first_publication_release: str
    first_publication_date: str
    change_date: str


@dataclass(frozen=True, slots=True)
class ReleaseIdentity:
    public_core_commit: str
    immutable_tag: str
    first_publication_date: str
    change_date: str
    newly_exposed_core_commits: tuple[ReleasePublicationRecord, ...]


@dataclass(frozen=True, slots=True)
class ReleaseLegalFingerprint:
    document_id: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ReleasePublicTrust:
    release_signing_key_sha256: str
    licensing_root_key_sha256: str
    licensing_issuer_catalog_sha256: str


@dataclass(frozen=True, slots=True)
class ReleaseManifestV1:
    edition: str
    version: str
    core_version: str
    release_identity: ReleaseIdentity
    legal_fingerprints: tuple[ReleaseLegalFingerprint, ...]
    public_trust: ReleasePublicTrust
    update_archives: tuple[ReleaseUpdateArchive, ...]
    installers: tuple[ReleaseInstaller, ...]
