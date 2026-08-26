"""SoAI - File explorer domain models and results [backend/core/files/explorer_models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.files.file_identity import FileIdentity

__all__ = (
    "BatchMetadataItemResult",
    "BatchMetadataResult",
    "BatchOperationItemResult",
    "BatchOperationResult",
    "FileEntryInfo",
    "FileExplorerDownloadArchive",
    "FileMetadata",
    "ListDirectoryResult",
    "SearchResult",
    "SearchResultEntry",
)

if TYPE_CHECKING:
    type FileEntryTypeId = Literal[
        "archive",
        "audio",
        "binary",
        "code",
        "config",
        "database",
        "data",
        "directory",
        "document",
        "image",
        "jpegImage",
        "json",
        "markdown",
        "model",
        "pdf",
        "plugin",
        "pngImage",
        "presentation",
        "shellScript",
        "spreadsheet",
        "text",
        "unknownFile",
        "video",
    ]


@dataclass(frozen=True, slots=True)
class FileExplorerDownloadArchive:
    archive_path: str
    download_filename: str
    identity: FileIdentity


@dataclass(frozen=True, slots=True)
class FileEntryInfo:
    name: str
    is_directory: bool
    size: int
    modified_at_ms: int
    mime_type: str
    type_id: FileEntryTypeId
    type_rank: int
    permissions: str


@dataclass(frozen=True, slots=True)
class FileMetadata:
    name: str
    path: str
    is_directory: bool
    size: int
    modified_at_ms: int
    mime_type: str
    type_id: FileEntryTypeId
    type_rank: int
    permissions: str
    sha256: str | None


@dataclass(frozen=True, slots=True)
class ListDirectoryResult:
    path: str
    entries: list[FileEntryInfo]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class BatchOperationItemResult:
    path: str
    success: bool
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class BatchOperationResult:
    total: int
    succeeded: int
    failed: int
    results: list[BatchOperationItemResult]


@dataclass(frozen=True, slots=True)
class BatchMetadataItemResult:
    path: str
    success: bool
    metadata: FileMetadata | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class BatchMetadataResult:
    total: int
    succeeded: int
    failed: int
    results: list[BatchMetadataItemResult]


@dataclass(frozen=True, slots=True)
class SearchResultEntry:
    path: str
    name: str
    is_directory: bool
    size: int
    modified_at_ms: int
    mime_type: str
    type_id: FileEntryTypeId
    type_rank: int
    permissions: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    query: str
    search_root: str
    entries: list[SearchResultEntry]
    total: int
    offset: int
    limit: int
    truncated: bool = False
    scanned_entries: int = 0
