"""SoAI - Core file explorer protocols [backend/core/files/protocols_explorer.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Protocol

from core.files.directory_listing_models import (
    DirectoryListingAdmission,
    DirectoryListingEntryType,
    DirectoryListingLocateResult,
    DirectoryListingPage,
    DirectoryListingSortColumn,
    DirectoryListingSortDirection,
)
from core.files.explorer_models import (
    BatchMetadataResult,
    BatchOperationResult,
    FileExplorerDownloadArchive,
    FileMetadata,
    ListDirectoryResult,
    SearchResult,
)

if TYPE_CHECKING:
    from core.concurrency.protocols import CancellationTokenProtocol

__all__ = (
    "FileExplorerBatchProtocol",
    "FileExplorerCoreProtocol",
    "FileExplorerDownloadProtocol",
    "FileExplorerListingProtocol",
    "FileExplorerSearchProtocol",
    "FileExplorerTaskLauncherProtocol",
    "FileSystemRootScopeProtocol",
)


class FileSystemRootScopeProtocol(Protocol):
    def resolve(self, virtual_path: str) -> str: ...
    def validate(self, real_path: str) -> str: ...
    def to_virtual_path(self, real_path: str) -> str: ...
    def canonicalize_virtual_path(self, virtual_path: str) -> str: ...
    def ensure_root_exists(self) -> None: ...

    @property
    def root_path(self) -> str: ...


class FileExplorerCoreProtocol(Protocol):
    def initialize(self) -> None: ...

    def create_workspace_scope(self, workspace_path: str) -> FileSystemRootScopeProtocol: ...

    def canonicalize_virtual_path(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> str: ...

    async def list_directory(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> ListDirectoryResult: ...

    async def get_metadata(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        include_hash: bool = False,
    ) -> FileMetadata: ...

    async def read_text_file(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> str: ...

    async def write_text_file(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        content: str,
    ) -> None: ...

    async def create_directory(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> None: ...

    async def delete_entry(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> None: ...

    async def move_entry(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_virtual_path: str,
        destination_virtual_path: str,
        *,
        overwrite: bool = False,
    ) -> None: ...

    async def copy_entry(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_virtual_path: str,
        destination_virtual_path: str,
        *,
        overwrite: bool = False,
    ) -> None: ...

    def resolve_real_path(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> str: ...

    def get_upload_destination(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        create_missing_parents: bool = False,
    ) -> str: ...

    async def move_staged_upload(
        self,
        *,
        root_scope: FileSystemRootScopeProtocol,
        temp_path: str,
        expected_size: int,
        virtual_destination: str,
        token: CancellationTokenProtocol,
        create_missing_parents: bool,
    ) -> str: ...

    async def notify_upload_complete(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> None: ...


class FileExplorerListingProtocol(Protocol):
    async def start_listing(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> DirectoryListingAdmission: ...

    async def get_page(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
        offset: int,
        limit: int,
        sort_column: DirectoryListingSortColumn,
        sort_direction: DirectoryListingSortDirection,
        entry_type: DirectoryListingEntryType,
    ) -> DirectoryListingPage: ...

    async def locate(
        self,
        *,
        listing_id: str,
        user_id: int,
        root_scope: FileSystemRootScopeProtocol,
        name: str,
        sort_column: DirectoryListingSortColumn,
        sort_direction: DirectoryListingSortDirection,
        entry_type: DirectoryListingEntryType,
    ) -> DirectoryListingLocateResult: ...

    async def release(self, *, listing_id: str, user_id: int) -> None: ...


class FileExplorerBatchProtocol(Protocol):
    async def delete_entries(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_paths: list[str],
    ) -> BatchOperationResult: ...

    async def move_entries(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> BatchOperationResult: ...

    async def copy_entries(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> BatchOperationResult: ...

    async def get_metadata(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_paths: list[str],
    ) -> BatchMetadataResult: ...


class FileExplorerDownloadProtocol(Protocol):
    async def create_archive(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_paths: tuple[str, ...],
        cancellation_event: threading.Event,
    ) -> FileExplorerDownloadArchive: ...


class FileExplorerTaskLauncherProtocol(Protocol):
    async def start_hash_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        virtual_path: str,
    ) -> str: ...

    async def start_delete_batch_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        virtual_paths: list[str],
    ) -> str: ...

    async def start_copy_batch_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> str: ...

    async def start_move_batch_task(
        self,
        root_scope: FileSystemRootScopeProtocol,
        user_id: int,
        source_paths: list[str],
        destination_dir: str,
        *,
        overwrite: bool = False,
    ) -> str: ...


class FileExplorerSearchProtocol(Protocol):
    def initialize(self) -> None: ...
    async def search_directory(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        query: str,
        *,
        offset: int = 0,
        limit: int | None = None,
        case_sensitive: bool = False,
        include_total: bool = False,
        cancellation_event: threading.Event | None = None,
    ) -> SearchResult: ...
