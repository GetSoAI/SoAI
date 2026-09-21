"""SoAI - Core files protocols [backend/core/files/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.files.protocols_archives import RarArchiveMemberProtocol, RarFileProtocol
from core.files.protocols_database import DatabaseFilesProtocol
from core.files.protocols_explorer import (
    FileExplorerBatchProtocol,
    FileExplorerCoreProtocol,
    FileExplorerDownloadProtocol,
    FileExplorerListingProtocol,
    FileExplorerSearchProtocol,
    FileExplorerTaskLauncherProtocol,
)
from core.files.protocols_manager import FileManagerProtocol
from core.files.protocols_streams import FileParserProtocol, SeekableStreamProtocol
from core.files.types import DocumentReadResult

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol
    from core.files.types import ParseProgressCallback

__all__ = (
    "DatabaseFilesProtocol",
    "DocumentReadResult",
    "DocumentReaderProtocol",
    "FileExplorerBatchProtocol",
    "FileExplorerCoreProtocol",
    "FileExplorerDownloadProtocol",
    "FileExplorerListingProtocol",
    "FileExplorerSearchProtocol",
    "FileExplorerTaskLauncherProtocol",
    "FileManagerProtocol",
    "FileParserProtocol",
    "FileParserRegistryFactoryProtocol",
    "FilesPathResolverProtocol",
    "RarArchiveMemberProtocol",
    "RarFileProtocol",
    "SeekableStreamProtocol",
)


class DocumentReaderProtocol(Protocol):
    async def read_document_to_text(
        self,
        *,
        file_path: str,
        ocr_language: str,
        parser_registry: dict[str, FileParserProtocol],
        parse_timeout_sec: float,
        max_chars: int,
        offset_chars: int,
        display_name: str | None = None,
        cancellation_token: CancellationTokenProtocol | None = None,
        progress_callback: ParseProgressCallback | None = None,
    ) -> DocumentReadResult: ...


class FilesPathResolverProtocol(Protocol):
    def resolve_path(self, path: str) -> str: ...


class FileParserRegistryFactoryProtocol(Protocol):
    def __call__(self) -> dict[str, FileParserProtocol]: ...
