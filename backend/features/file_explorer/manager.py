"""SoAI - File explorer core manager service [backend/features/file_explorer/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exceptions import ValidationError
from core.files.explorer_models import FileMetadata, ListDirectoryResult
from core.files.protocols_explorer import FileSystemRootScopeProtocol
from core.logging.trace import get_logger
from features.file_explorer import entry_mutation_service, transfer_service, upload_mutation_service
from features.file_explorer.dependencies import (
    FileExplorerManagerDependencies,
)
from features.file_explorer.entry_queries import (
    build_file_metadata,
    build_list_directory_result,
)
from features.file_explorer.path_resolution import (
    canonicalize_virtual_path,
    resolve_existing_real_path,
    resolve_upload_destination,
)
from features.file_explorer.runtime_settings import resolve_file_explorer_runtime_settings
from features.file_explorer.workspace_scope import FileSystemRootScope

__all__ = ("FileExplorerManager",)

LOGGER_NAME = "SoAI.features.file_explorer.manager"


class FileExplorerManager:
    __slots__ = (
        "_allow_symlinks",
        "_config",
        "_database_path",
        "_event_bus",
        "_files",
        "_listing_pagination_limit",
        "_mutation_locks",
        "_secure_ops",
        "_storage_manager",
        "_temp_dir",
        "_text_preview_limit_bytes",
    )

    def __init__(self, deps: FileExplorerManagerDependencies) -> None:
        self._config = deps.config
        self._files = deps.files
        self._event_bus = deps.event_bus
        self._storage_manager = deps.storage_manager
        self._secure_ops = deps.secure_ops
        self._allow_symlinks = False
        self._database_path: str | None = None
        self._text_preview_limit_bytes = 0
        self._listing_pagination_limit = 100
        self._temp_dir = ""
        self._mutation_locks = deps.mutation_locks

    def initialize(self) -> None:
        logger = get_logger(LOGGER_NAME)
        settings = resolve_file_explorer_runtime_settings(self._config, self._files)
        self._allow_symlinks = settings.allow_symlinks
        self._text_preview_limit_bytes = settings.text_preview_limit_bytes
        self._listing_pagination_limit = settings.listing_pagination_limit
        self._temp_dir = settings.temp_dir
        self._database_path = settings.database_path
        logger.debug("FileExplorerManager initialized.")

    def create_workspace_scope(self, workspace_path: str) -> FileSystemRootScopeProtocol:
        if not isinstance(workspace_path, str) or not workspace_path.strip():
            raise ValidationError("workspace_path must be a non-empty string.")
        resolved_root = self._files.resolve_path(workspace_path)
        root_scope = FileSystemRootScope(
            root_path=resolved_root,
            allow_symlinks=self._allow_symlinks,
        )
        root_scope.ensure_root_exists()
        return root_scope

    def canonicalize_virtual_path(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> str:
        return canonicalize_virtual_path(root_scope, virtual_path)

    async def list_directory(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> ListDirectoryResult:
        virtual_path = self.canonicalize_virtual_path(root_scope, virtual_path)
        effective_limit = limit if limit is not None else self._listing_pagination_limit
        real_path = root_scope.resolve(virtual_path)
        return await asyncio.to_thread(
            build_list_directory_result,
            secure_ops=self._secure_ops,
            real_path=real_path,
            virtual_path=virtual_path,
            offset=offset,
            limit=effective_limit,
        )

    async def get_metadata(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        include_hash: bool = False,
    ) -> FileMetadata:
        virtual_path = self.canonicalize_virtual_path(root_scope, virtual_path)
        real_path = root_scope.resolve(virtual_path)
        return await asyncio.to_thread(
            build_file_metadata,
            secure_ops=self._secure_ops,
            real_path=real_path,
            virtual_path=virtual_path,
            include_hash=include_hash,
        )

    async def read_text_file(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> str:
        virtual_path = self.canonicalize_virtual_path(root_scope, virtual_path)
        real_path = root_scope.resolve(virtual_path)
        return await asyncio.to_thread(
            self._secure_ops.read_text,
            real_path,
            max_bytes=self._text_preview_limit_bytes,
        )

    async def write_text_file(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        content: str,
    ) -> None:
        await entry_mutation_service.write_text_file(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            storage_manager=self._storage_manager,
            mutation_locks=self._mutation_locks,
            event_bus=self._event_bus,
            virtual_path=virtual_path,
            content=content,
            temp_dir=self._temp_dir,
            database_path=self._database_path,
        )

    async def create_directory(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> None:
        await entry_mutation_service.create_directory(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            storage_manager=self._storage_manager,
            mutation_locks=self._mutation_locks,
            event_bus=self._event_bus,
            virtual_path=virtual_path,
            database_path=self._database_path,
        )

    async def delete_entry(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> None:
        await entry_mutation_service.delete_entry(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            mutation_locks=self._mutation_locks,
            event_bus=self._event_bus,
            virtual_path=virtual_path,
            database_path=self._database_path,
        )

    async def move_entry(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_virtual_path: str,
        destination_virtual_path: str,
        *,
        overwrite: bool = False,
    ) -> None:
        await transfer_service.move_entry(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            mutation_locks=self._mutation_locks,
            event_bus=self._event_bus,
            source_virtual_path=source_virtual_path,
            destination_virtual_path=destination_virtual_path,
            overwrite=overwrite,
            database_path=self._database_path,
        )

    async def copy_entry(
        self,
        root_scope: FileSystemRootScopeProtocol,
        source_virtual_path: str,
        destination_virtual_path: str,
        *,
        overwrite: bool = False,
    ) -> None:
        await transfer_service.copy_entry(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            mutation_locks=self._mutation_locks,
            event_bus=self._event_bus,
            storage_manager=self._storage_manager,
            source_virtual_path=source_virtual_path,
            destination_virtual_path=destination_virtual_path,
            overwrite=overwrite,
            database_path=self._database_path,
        )

    def resolve_real_path(self, root_scope: FileSystemRootScopeProtocol, virtual_path: str) -> str:
        return resolve_existing_real_path(root_scope, virtual_path)

    def get_upload_destination(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
        *,
        create_missing_parents: bool = False,
    ) -> str:
        return resolve_upload_destination(
            root_scope,
            self._secure_ops,
            virtual_path,
            create_missing_parents=create_missing_parents,
        )

    async def move_staged_upload(
        self,
        *,
        root_scope: FileSystemRootScopeProtocol,
        temp_path: str,
        expected_size: int,
        virtual_destination: str,
        token: CancellationTokenProtocol,
        create_missing_parents: bool,
    ) -> str:
        return await upload_mutation_service.move_staged_upload(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            mutation_locks=self._mutation_locks,
            storage_manager=self._storage_manager,
            temp_path=temp_path,
            expected_size=expected_size,
            virtual_destination=virtual_destination,
            token=token,
            create_missing_parents=create_missing_parents,
            database_path=self._database_path,
            allow_symlinks=self._allow_symlinks,
        )

    async def notify_upload_complete(
        self,
        root_scope: FileSystemRootScopeProtocol,
        virtual_path: str,
    ) -> None:
        await upload_mutation_service.notify_upload_complete(
            root_scope=root_scope,
            secure_ops=self._secure_ops,
            mutation_locks=self._mutation_locks,
            event_bus=self._event_bus,
            virtual_path=virtual_path,
        )
