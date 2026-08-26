"""SoAI - File explorer internal protocols [backend/features/file_explorer/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol

from core.files.protocols_explorer import FileSystemRootScopeProtocol
from features.file_explorer.directory_listing_state import DirectoryListingRecord

if TYPE_CHECKING:
    from core.files.explorer_models import FileMetadata
    from core.hardware.protocols_storage import DiskSpaceReservationLeaseProtocol

__all__ = (
    "FileExplorerCoreProtocol",
    "DirectoryListingBuilderProtocol",
    "DirectoryListingRegistryProtocol",
    "FileExplorerDeleteBatchWorkerProtocol",
    "FileExplorerHashWorkerProtocol",
    "FileExplorerTransferBatchWorkerProtocol",
    "SecureFileOpsProtocol",
)


class DirectoryListingBuilderProtocol(Protocol):
    async def build_listing_task(
        self,
        *,
        listing_id: str,
        user_id: int,
        workspace_path: str,
        virtual_path: str,
        task_id: str,
    ) -> None: ...


class DirectoryListingRegistryProtocol(Protocol):
    async def admit(
        self,
        *,
        listing_id: str,
        user_id: int,
        workspace_path: str,
        virtual_path: str,
    ) -> DirectoryListingRecord: ...

    async def attach_task(self, listing_id: str, *, task_id: str) -> None: ...

    async def wait_for_task_id(self, listing_id: str, *, user_id: int) -> str: ...

    async def mark_ready(
        self,
        listing_id: str,
        *,
        snapshot_path: str,
    ) -> bool: ...

    async def mark_failed(self, listing_id: str) -> None: ...

    async def get(
        self,
        listing_id: str,
        *,
        user_id: int,
    ) -> DirectoryListingRecord | None: ...

    async def reap_expired(self) -> list[DirectoryListingRecord]: ...

    async def release(self, listing_id: str, *, user_id: int) -> bool: ...


class SecureFileOpsProtocol(Protocol):
    def list_directory(self, real_path: str) -> list[str]: ...

    def stat_entry(self, directory_path: str, entry_name: str) -> os.stat_result: ...

    def stat_path(self, real_path: str) -> os.stat_result: ...

    def read_text(self, real_path: str, *, max_bytes: int) -> str: ...

    def read_bytes_sample(self, real_path: str, *, max_bytes: int) -> bytes: ...

    def write_text_atomic(
        self,
        real_path: str,
        content: str,
        *,
        temp_dir: str,
        root_path: str,
    ) -> None: ...

    def create_directory(self, real_path: str) -> None: ...

    def remove_file(self, real_path: str) -> None: ...

    def remove_directory_recursive(self, real_path: str) -> None: ...

    def move_entry(self, source_path: str, destination_path: str) -> None: ...

    def copy_file(
        self,
        source_path: str,
        destination_path: str,
        *,
        write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    ) -> None: ...

    def copy_directory(
        self,
        source_path: str,
        destination_path: str,
        *,
        write_reservation: DiskSpaceReservationLeaseProtocol | None = None,
    ) -> None: ...


class FileExplorerCoreProtocol(Protocol):
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

    async def get_metadata(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        include_hash: bool = False,
    ) -> FileMetadata: ...


class FileExplorerHashWorkerProtocol(Protocol):
    async def compute_hash_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        virtual_path: str,
        *,
        task_id: str,
    ) -> None: ...


class FileExplorerDeleteBatchWorkerProtocol(Protocol):
    async def delete_batch_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        virtual_paths: list[str],
        *,
        task_id: str,
    ) -> None: ...


class FileExplorerTransferBatchWorkerProtocol(Protocol):
    async def copy_batch_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        source_paths: list[str],
        destination_dir: str,
        *,
        task_id: str,
        overwrite: bool = False,
    ) -> None: ...

    async def move_batch_async(
        self,
        user_id: int,
        workspace_path_resolved: str,
        source_paths: list[str],
        destination_dir: str,
        *,
        task_id: str,
        overwrite: bool = False,
    ) -> None: ...
