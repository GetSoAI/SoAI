"""SoAI - Backup manifest typing [backend/core/backup/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

if TYPE_CHECKING:
    from core.licensing.backup_recovery import LicensingRecoverySummary

    type BackupManifestEntry = BackupFileEntry | BackupDirectoryEntry
    type BackupManifestFiles = dict[str, BackupManifestEntry]
else:
    BackupManifestEntry = dict
    BackupManifestFiles = dict

__all__ = (
    "BackupCreateResult",
    "BackupDirectoryEntry",
    "BackupFileEntry",
    "BackupManifest",
)


class BackupFileEntry(TypedDict):
    type: Literal["file"]
    sha256: str
    size: int
    integrity_ok: NotRequired[bool]


class BackupDirectoryEntry(TypedDict):
    type: Literal["directory"]
    sha256: str
    size: int


class BackupManifest(TypedDict):
    backup_id: str
    timestamp_ms: int
    timestamp_iso: str
    soai_version: str
    files: BackupManifestFiles
    total_size_bytes: int
    sqlite_integrity_ok: bool
    targets_enabled: dict[str, bool]
    targets_completed: dict[str, bool]
    licensing_recovery: LicensingRecoverySummary


class BackupCreateResult(TypedDict):
    backup_id: str
    backup_path: str
    manifest: BackupManifest
    success: bool
    targets_enabled: dict[str, bool]
    targets_completed: dict[str, bool]
