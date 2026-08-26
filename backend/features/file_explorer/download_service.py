"""SoAI - File explorer download archive service [backend/features/file_explorer/download_service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import threading
from dataclasses import dataclass

from core.concurrency.path_tree_lock import AsyncPathTreeLock
from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.files.explorer_models import FileExplorerDownloadArchive
from core.files.protocols import FilesPathResolverProtocol
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from core.hardware.protocols_storage import StorageManagerProtocol
from features.file_explorer.download_archive import create_download_archive
from features.file_explorer.path_resolution import resolve_download_archive_real_path
from features.file_explorer.runtime_settings import resolve_file_explorer_runtime_settings

__all__ = (
    "FileExplorerDownloadService",
    "FileExplorerDownloadServiceDependencies",
)


@dataclass(frozen=True, slots=True)
class FileExplorerDownloadServiceDependencies:
    config: ConfigProtocol
    files: FilesPathResolverProtocol
    storage_manager: StorageManagerProtocol
    mutation_locks: AsyncPathTreeLock

    def __post_init__(self) -> None:
        require_dependencies(
            owner="FileExplorerDownloadServiceDependencies",
            config=self.config,
            files=self.files,
            mutation_locks=self.mutation_locks,
            storage_manager=self.storage_manager,
        )


class FileExplorerDownloadService:
    __slots__ = (
        "_config",
        "_files",
        "_mutation_locks",
        "_maximum_archive_bytes",
        "_maximum_members",
        "_storage_manager",
        "_temp_directory",
    )

    def __init__(self, deps: FileExplorerDownloadServiceDependencies) -> None:
        self._config = deps.config
        self._files = deps.files
        self._mutation_locks = deps.mutation_locks
        self._maximum_archive_bytes = 0
        self._maximum_members = 0
        self._storage_manager = deps.storage_manager
        self._temp_directory = ""

    def initialize(self) -> None:
        settings = resolve_file_explorer_runtime_settings(self._config, self._files)
        self._maximum_archive_bytes = settings.maximum_download_archive_bytes
        self._maximum_members = settings.maximum_download_archive_members
        self._temp_directory = settings.temp_dir

    async def create_archive(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_paths: tuple[str, ...],
        cancellation_event: threading.Event,
    ) -> FileExplorerDownloadArchive:
        real_paths = tuple(
            resolve_download_archive_real_path(root_scope, virtual_path)
            for virtual_path in virtual_paths
        )
        return await create_download_archive(
            root_path=root_scope.root_path,
            selected_paths=real_paths,
            temp_directory=self._temp_directory,
            maximum_members=self._maximum_members,
            maximum_archive_bytes=self._maximum_archive_bytes,
            storage_manager=self._storage_manager,
            mutation_locks=self._mutation_locks,
            cancellation_event=cancellation_event,
        )
