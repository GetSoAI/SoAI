"""SoAI - File explorer download archive planning models [backend/features/file_explorer/download_archive_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.files.file_identity import FileIdentity

__all__ = (
    "DownloadArchiveDirectory",
    "DownloadArchiveEntry",
    "DownloadArchivePlan",
)


@dataclass(frozen=True, slots=True)
class DownloadArchiveEntry:
    source_path: str
    archive_path: str
    identity: FileIdentity

    @property
    def is_directory(self) -> bool:
        return self.identity.is_directory


@dataclass(frozen=True, slots=True)
class DownloadArchiveDirectory:
    source_path: str
    identity: FileIdentity
    child_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DownloadArchivePlan:
    entries: tuple[DownloadArchiveEntry, ...]
    directories: tuple[DownloadArchiveDirectory, ...]
    required_bytes: int
    download_filename: str
