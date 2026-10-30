"""SoAI - Immutable ZIP archive creation models [backend/core/archives/zip_creation_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.files.file_identity import FileIdentity

__all__ = (
    "ZipArchiveDirectory",
    "ZipArchiveEntry",
    "ZipArchivePlan",
    "ZipArchiveResult",
)


@dataclass(frozen=True, slots=True)
class ZipArchiveEntry:
    source_path: str
    archive_path: str
    identity: FileIdentity

    @property
    def is_directory(self) -> bool:
        return self.identity.is_directory


@dataclass(frozen=True, slots=True)
class ZipArchiveDirectory:
    source_path: str
    identity: FileIdentity
    child_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ZipArchivePlan:
    entries: tuple[ZipArchiveEntry, ...]
    directories: tuple[ZipArchiveDirectory, ...]
    required_bytes: int
    download_filename: str


@dataclass(frozen=True, slots=True)
class ZipArchiveResult:
    archive_path: str
    download_filename: str
    identity: FileIdentity
